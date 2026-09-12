"""
finance/services/sale_service.py

Criação, edição e exclusão de vendas.

Este é o ponto onde estoque e dinheiro se encontram, e por isso concentra as
decisões mais delicadas do módulo:

TRANSAÇÃO EXPLÍCITA — E POR QUE NÃO BASTA O `ATOMIC_REQUESTS`
    O projeto usa `ATOMIC_REQUESTS = True`, mas isso NÃO é suficiente aqui: as
    views existentes capturam `except Exception` e devolvem uma mensagem de
    erro (ex.: operations/views/ocorrencias.py). Quando a view engole a
    exceção, a transação do request segue viva e COMITA o que já foi escrito —
    ou seja, uma venda de 3 lotes que falhasse no terceiro gravaria os dois
    primeiros e daria baixa no estoque deles. O `with transaction.atomic()`
    dentro do serviço cria um savepoint próprio, que desfaz tudo mesmo que
    quem chamou capture o erro.

ORDEM DE BLOQUEIO DETERMINÍSTICA
    As linhas são processadas ordenadas por `animal_category_id`. Duas vendas
    simultâneas na mesma fazenda passam a pegar os locks na mesma ordem, o que
    elimina a chance de deadlock.

MESMA CATEGORIA EM DUAS LINHAS
    É permitido de propósito (dois lotes com preços por quilo diferentes). A
    validação de estoque precisa somar as quantidades por categoria antes de
    comparar com o saldo — validar linha a linha deixaria passar uma venda que
    no total estoura o estoque. Como as chamadas a `execute_saida` acontecem na
    mesma transação e cada uma relê o saldo com `select_for_update`, a segunda
    linha já enxerga o saldo descontado pela primeira.

COMPATIBILIDADE COM OS RELATÓRIOS ANTIGOS
    Cada lote continua gravando `peso`, `preco_total` e `observacao` no
    `metadata` do `AnimalMovement`, sempre como `str(Decimal)` (nunca float).
    É o que mantém o Relatório por Fazenda, o PDF de ocorrências e a tela de
    auditoria funcionando sem qualquer alteração.
"""
import logging
from collections import defaultdict
from decimal import Decimal

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, ProtectedError
from django.utils import timezone

from finance.models import (
    DeletedObjectType,
    EntrySource,
    EntryType,
    FinanceDeletionLog,
    FinancialEntry,
    Sale,
    SaleItem,
    SaleStatus,
)
from finance.utils.money import quantize_money
from inventory.domain import OperationType
from inventory.models import AnimalMovement, AnimalMovementCancellation, FarmStockBalance
from inventory.services import MovementService

logger = logging.getLogger(__name__)


class SaleService:
    """Regras de negócio das vendas. Views nunca escrevem direto nos modelos."""

    # ────────────────────────────────────────────────────────────────────
    # CRIAÇÃO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def create(*, client, farm, date, items, user, notes='', ip_address=None) -> Sale:
        """
        Registra uma venda com um ou mais lotes de animais.

        Args:
            client: instância de operations.Client
            farm:   instância de farms.Farm
            date:   date da venda
            items:  lista de dicts com as chaves
                    animal_category (instância), quantity (int),
                    total_weight (Decimal|None), price_per_kg (Decimal|None),
                    total_amount (Decimal|None)
            user:   quem está registrando
            notes:  observação livre
            ip_address: IP de origem, para auditoria

        Returns:
            A Sale criada, com os itens já persistidos.

        Raises:
            ValidationError: nenhuma linha informada, quantidade inválida ou
                             estoque insuficiente.
        """
        if not items:
            raise ValidationError("Informe ao menos um tipo de animal na venda.")

        with transaction.atomic():
            SaleService._assert_stock_available(farm, items)

            sale = Sale.objects.create(
                client=client,
                farm=farm,
                date=date,
                notes=notes or '',
                status=SaleStatus.ATIVA,
                created_by=user,
            )

            SaleService._create_items(sale, items, user, ip_address, notes)
            SaleService._refresh_totals(sale)
            SaleService._sync_financial_entry(sale, user)

        SaleService._invalidate_farm_cache(str(farm.id))
        logger.warning(
            "[VENDA] Criada %s | Cliente: %s | Fazenda: %s | %s lote(s) | "
            "Total: %s | Por: %s",
            sale.id, client.name, farm.name, len(items),
            sale.total_amount, user.username,
        )
        return sale

    # ────────────────────────────────────────────────────────────────────
    # EDIÇÃO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def update(*, sale, client, farm, date, items, user, notes='', ip_address=None) -> Sale:
        """
        Substitui completamente o conteúdo de uma venda.

        Estratégia: devolve ao estoque tudo o que a venda tinha retirado, apaga
        as movimentações antigas e recria a venda com as linhas novas — tudo
        num bloco atômico. Ou a venda inteira muda, ou nada muda.

        Raises:
            ValidationError: venda cancelada, venda com movimentação já
                             estornada, ou estoque insuficiente para a nova
                             composição.
        """
        if not items:
            raise ValidationError("Informe ao menos um tipo de animal na venda.")

        with transaction.atomic():
            sale = Sale.objects.select_for_update().get(pk=sale.pk)

            if sale.status == SaleStatus.CANCELADA:
                raise ValidationError(
                    "Esta venda está cancelada e não pode ser editada. "
                    "Registre uma venda nova."
                )

            SaleService._assert_no_cancelled_movements(
                sale, acao="editar",
            )

            # Devolve o estoque das linhas atuais antes de validar as novas —
            # senão uma edição que apenas troca o preço seria recusada por
            # "estoque insuficiente" contra o saldo que ela mesma ocupa.
            SaleService._release_items(sale)

            SaleService._assert_stock_available(farm, items)

            sale.client = client
            sale.farm = farm
            sale.date = date
            sale.notes = notes or ''
            sale.save(update_fields=['client', 'farm', 'date', 'notes', 'updated_at'])

            SaleService._create_items(sale, items, user, ip_address, notes)
            SaleService._refresh_totals(sale)
            SaleService._sync_financial_entry(sale, user)

        SaleService._invalidate_farm_cache(str(farm.id))
        logger.warning(
            "[VENDA] Editada %s | Cliente: %s | %s lote(s) | Total: %s | Por: %s",
            sale.id, client.name, len(items), sale.total_amount, user.username,
        )
        return sale

    # ────────────────────────────────────────────────────────────────────
    # EXCLUSÃO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def delete(*, sale, user, reason='', ip_address=None) -> dict:
        """
        Apaga a venda de verdade: devolve o estoque, remove as movimentações,
        os lotes e os lançamentos financeiros.

        Antes de apagar, grava um FinanceDeletionLog com o retrato completo do
        que existia — é o único lugar onde a venda continuará visível depois,
        já que a tela de auditoria lê a tabela viva de movimentações.

        Raises:
            ValidationError: se alguma movimentação da venda já foi estornada
                             (nesse caso o histórico de estorno precisa ser
                             preservado e a exclusão é recusada).
        """
        with transaction.atomic():
            # Sem select_related junto do select_for_update: no PostgreSQL o
            # FOR UPDATE alcança todas as tabelas do JOIN, e travaríamos também
            # as linhas do cliente e da fazenda — segurando operações que nada
            # têm a ver com esta venda.
            sale = Sale.objects.select_for_update().get(pk=sale.pk)

            SaleService._assert_no_cancelled_movements(sale, acao="apagar")

            snapshot = SaleService._build_snapshot(sale)
            farm_id = str(sale.farm_id)
            resumo = {
                'cliente': sale.client.name,
                'data': sale.date,
                'total': sale.total_amount,
                'lotes': sale.items.count(),
            }

            FinanceDeletionLog.objects.create(
                object_type=DeletedObjectType.VENDA,
                object_id=sale.id,
                client=sale.client,
                object_date=sale.date,
                amount=sale.total_amount,
                snapshot=snapshot,
                reason=reason or '',
                deleted_by=user,
                ip_address=ip_address,
            )

            # Devolve o estoque e remove as movimentações do ledger.
            SaleService._release_items(sale)

            # FinancialEntry cai por CASCADE, mas apagamos explicitamente para
            # deixar a intenção visível no código.
            sale.entries.all().delete()
            sale.delete()

        SaleService._invalidate_farm_cache(farm_id)
        logger.warning(
            "[VENDA] APAGADA | Cliente: %s | Data: %s | Total: %s | "
            "Lotes: %s | Por: %s | Motivo: %s",
            resumo['cliente'], resumo['data'], resumo['total'],
            resumo['lotes'], user.username, reason or '(não informado)',
        )
        return resumo

    # ────────────────────────────────────────────────────────────────────
    # HELPERS — ESTOQUE
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def _assert_stock_available(farm, items) -> None:
        """
        Recusa a venda quando a SOMA das quantidades de uma categoria não cabe
        no estoque.

        Somar por categoria é essencial: a mesma categoria pode aparecer em
        várias linhas, e validar linha a linha deixaria passar uma venda que no
        total estoura o saldo.

        Esta checagem é uma cortesia com o usuário (mensagem clara antes de
        qualquer escrita). A garantia real é o `select_for_update` dentro do
        MovementService mais o CheckConstraint do banco.
        """
        needed = defaultdict(int)
        for item in items:
            category = item['animal_category']
            quantity = int(item['quantity'])
            if quantity <= 0:
                raise ValidationError(
                    f"A quantidade de '{category.name}' deve ser maior que zero."
                )
            needed[category] += quantity

        balances = {
            b.animal_category_id: b.current_quantity
            for b in FarmStockBalance.objects.filter(
                farm=farm, animal_category__in=list(needed.keys()),
            )
        }

        for category, quantity in needed.items():
            available = balances.get(category.id, 0)
            if quantity > available:
                raise ValidationError(
                    f"Estoque insuficiente de '{category.name}' em {farm.name}. "
                    f"Disponível: {available}, solicitado nesta venda: {quantity}."
                )

    @staticmethod
    def _create_items(sale, items, user, ip_address, notes) -> None:
        """
        Cria cada lote e a sua baixa de estoque.

        Ordena por categoria para que duas vendas simultâneas na mesma fazenda
        peguem os locks sempre na mesma ordem (prevenção de deadlock).
        """
        ordered = sorted(
            enumerate(items),
            key=lambda pair: (str(pair[1]['animal_category'].id), pair[0]),
        )

        for line_order, (original_index, item) in enumerate(ordered):
            category = item['animal_category']
            quantity = int(item['quantity'])
            total_weight = item.get('total_weight')
            price_per_kg = item.get('price_per_kg')
            total_amount = quantize_money(item.get('total_amount'))

            movement = MovementService.execute_saida(
                farm_id=str(sale.farm_id),
                animal_category_id=str(category.id),
                operation_type=OperationType.VENDA,
                quantity=quantity,
                user=user,
                client_id=str(sale.client_id),
                timestamp=sale.date,
                metadata=SaleService._build_movement_metadata(
                    sale=sale,
                    total_weight=total_weight,
                    price_per_kg=price_per_kg,
                    total_amount=total_amount,
                    notes=notes,
                ),
                ip_address=ip_address,
            )

            SaleItem.objects.create(
                sale=sale,
                animal_category=category,
                movement=movement,
                quantity=quantity,
                total_weight=total_weight,
                price_per_kg=price_per_kg,
                total_amount=total_amount,
                line_order=original_index,
            )

    @staticmethod
    def _release_items(sale) -> None:
        """
        Devolve ao estoque tudo o que os lotes da venda retiraram e apaga as
        movimentações correspondentes.

        Ordem obrigatória: primeiro o SaleItem, depois o AnimalMovement. O
        `SaleItem.movement` é PROTECT justamente para impedir que alguém apague
        a movimentação por outro caminho; aqui desfazemos o vínculo antes.

        Usa `QuerySet.delete()` de propósito: ele não passa pelo
        `AnimalMovement.delete()` (que proíbe exclusão, e continua proibindo
        para o resto do sistema) e mesmo assim dispara o `post_delete`, então o
        django-simple-history registra a exclusão no histórico.
        """
        items = list(sale.items.select_related('animal_category').all())
        movement_ids = [i.movement_id for i in items if i.movement_id]

        for item in sorted(items, key=lambda i: str(i.animal_category_id)):
            if item.movement_id is None:
                continue
            # Lock pessimista primeiro; o F() logo abaixo é seguro porque a
            # linha já está travada. Mesmo padrão do MovementService — e evita
            # o full_clean() que o FarmStockBalance.save() dispararia.
            balance = (
                FarmStockBalance.objects
                .select_for_update()
                .get(farm_id=sale.farm_id, animal_category_id=item.animal_category_id)
            )
            FarmStockBalance.objects.filter(id=balance.id).update(
                current_quantity=F('current_quantity') + item.quantity,
                version=F('version') + 1,
                updated_at=timezone.now(),
            )

        sale.items.all().delete()

        if movement_ids:
            try:
                AnimalMovement.objects.filter(id__in=movement_ids).delete()
            except ProtectedError as exc:
                # Não deveria acontecer: _assert_no_cancelled_movements já
                # barrou o único caso conhecido. Traduzimos assim mesmo para o
                # usuário não receber um erro 500 cru.
                raise ValidationError(
                    "Não foi possível remover as movimentações de estoque desta "
                    "venda porque elas possuem registros vinculados."
                ) from exc

    @staticmethod
    def _assert_no_cancelled_movements(sale, acao: str) -> None:
        """
        Barra edição/exclusão de venda que tenha algum lote já estornado.

        O registro de estorno (`AnimalMovementCancellation`) é imutável por
        contrato e protege a movimentação contra exclusão. Em vez de deixar o
        banco levantar um ProtectedError cru, recusamos aqui com uma mensagem
        que o usuário entende.
        """
        movement_ids = list(
            sale.items.filter(movement__isnull=False).values_list('movement_id', flat=True)
        )
        if not movement_ids:
            return

        if AnimalMovementCancellation.objects.filter(movement_id__in=movement_ids).exists():
            raise ValidationError(
                f"Não é possível {acao} esta venda: um ou mais lotes já foram "
                f"cancelados/estornados e esse histórico precisa ser preservado."
            )

    # ────────────────────────────────────────────────────────────────────
    # HELPERS — DINHEIRO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def _refresh_totals(sale) -> None:
        """Recalcula os totais em cache a partir dos lotes."""
        total_quantity = 0
        total_weight = None
        total_amount = None

        for item in sale.items.all():
            total_quantity += item.quantity
            if item.total_weight is not None:
                total_weight = (total_weight or Decimal('0')) + item.total_weight
            if item.total_amount is not None:
                total_amount = (total_amount or Decimal('0')) + item.total_amount

        sale.total_quantity = total_quantity
        sale.total_weight = total_weight
        sale.total_amount = quantize_money(total_amount)
        sale.save(update_fields=[
            'total_quantity', 'total_weight', 'total_amount', 'updated_at',
        ])

    @staticmethod
    def _sync_financial_entry(sale, user) -> None:
        """
        Deixa o extrato do cliente coerente com a venda.

        Uma venda tem no máximo um lançamento de débito. Vendas sem preço — o
        caso comum no histórico importado — não geram lançamento nenhum, e
        passam a gerar assim que alguém preencher o valor.
        """
        sale.entries.all().delete()

        if sale.status != SaleStatus.ATIVA:
            return
        if sale.total_amount is None or sale.total_amount <= 0:
            return

        FinancialEntry.objects.create(
            client=sale.client,
            date=sale.date,
            entry_type=EntryType.DEBITO,
            amount=sale.total_amount,
            source_type=EntrySource.VENDA,
            sale=sale,
            description=f"Venda de {sale.total_quantity} animal(is)",
            created_by=user,
        )

    @staticmethod
    def _build_movement_metadata(*, sale, total_weight, price_per_kg, total_amount, notes):
        """
        Metadata do AnimalMovement.

        Mantém exatamente as chaves que o resto do sistema já lê (`observacao`,
        `peso`, `preco_total`), sempre como texto de Decimal — nunca float —
        para não quebrar o Relatório por Fazenda, o PDF de ocorrências nem a
        tela de auditoria. As chaves novas são só rastreabilidade.
        """
        metadata = {'observacao': notes or ''}
        if total_weight is not None:
            metadata['peso'] = str(total_weight)
        if total_amount is not None:
            metadata['preco_total'] = str(total_amount)
        if price_per_kg is not None:
            metadata['preco_kg'] = str(price_per_kg)
        metadata['_sale_id'] = str(sale.id)
        return metadata

    @staticmethod
    def _build_snapshot(sale) -> dict:
        """Retrato completo da venda, para o log de exclusões."""
        return {
            'venda': {
                'id': str(sale.id),
                'data': sale.date.isoformat(),
                'cliente': sale.client.name,
                'cliente_id': str(sale.client_id),
                'fazenda': sale.farm.name,
                'fazenda_id': str(sale.farm_id),
                'observacao': sale.notes,
                'situacao': sale.status,
                'origem': sale.origin,
                'quantidade_total': sale.total_quantity,
                'peso_total': str(sale.total_weight) if sale.total_weight is not None else None,
                'valor_total': str(sale.total_amount) if sale.total_amount is not None else None,
                'registrada_por': sale.created_by.username,
                'registrada_em': sale.created_at.isoformat() if sale.created_at else None,
            },
            'lotes': [
                {
                    'tipo_animal': item.animal_category.name,
                    'tipo_animal_id': str(item.animal_category_id),
                    'quantidade': item.quantity,
                    'peso_total': str(item.total_weight) if item.total_weight is not None else None,
                    'preco_kg': str(item.price_per_kg) if item.price_per_kg is not None else None,
                    'valor_total': str(item.total_amount) if item.total_amount is not None else None,
                    'movimentacao_id': str(item.movement_id) if item.movement_id else None,
                }
                for item in sale.items.select_related('animal_category').all()
            ],
            'lancamentos': [
                {
                    'id': str(entry.id),
                    'data': entry.date.isoformat(),
                    'natureza': entry.entry_type,
                    'valor': str(entry.amount),
                    'descricao': entry.description,
                }
                for entry in sale.entries.all()
            ],
        }

    @staticmethod
    def _invalidate_farm_cache(farm_id: str) -> None:
        """Mesmas chaves invalidadas pelo OccurrenceService."""
        cache.delete(f'farm_summary_{farm_id}')
        cache.delete(f'farm_history_{farm_id}')
        cache.delete(f'farm_stock_{farm_id}')
        cache.delete('farms_list')

"""
Confere a integridade do módulo financeiro.

Rode depois de cada deploy e sempre que algo parecer estranho nos saldos.
Por padrão só relata; com `--corrigir` ele conserta o que é seguro consertar.

    python manage.py verificar_financeiro
    python manage.py verificar_financeiro --corrigir
    python manage.py verificar_financeiro --cliente <uuid>

O que é verificado:
  1. Toda venda de VENDA no ledger tem um lote correspondente (nada ficou fora
     do backfill).
  2. Todo lote aponta para uma movimentação que ainda existe.
  3. Os totais em cache da venda batem com a soma dos lotes.
  4. O extrato bate com as vendas e pagamentos: uma venda ativa com valor tem
     exatamente um débito do mesmo valor; um pagamento tem exatamente um
     crédito.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Sum

from finance.models import (
    EntrySource,
    EntryType,
    FinancialEntry,
    Payment,
    Sale,
    SaleItem,
    SaleStatus,
)
from finance.utils.money import quantize_money
from inventory.models import AnimalMovement

ZERO = Decimal('0.00')


class Command(BaseCommand):
    help = "Confere a integridade das vendas, pagamentos e saldos do financeiro."

    def add_arguments(self, parser):
        parser.add_argument(
            '--corrigir',
            action='store_true',
            help="Corrige o que for seguro (totais em cache e lançamentos do extrato).",
        )
        parser.add_argument(
            '--cliente',
            type=str,
            default=None,
            help="Limita a verificação a um cliente (UUID).",
        )

    def handle(self, *args, **options):
        corrigir = options['corrigir']
        cliente_id = options['cliente']

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nVerificação de integridade do financeiro\n" + "=" * 60
        ))
        if corrigir:
            self.stdout.write(self.style.WARNING("Modo CORRIGIR ativo — alterações serão gravadas.\n"))
        else:
            self.stdout.write("Modo somente leitura. Use --corrigir para aplicar correções.\n")

        problemas = 0
        problemas += self._checar_vendas_orfas(cliente_id)
        problemas += self._checar_lotes_sem_movimentacao(cliente_id)
        problemas += self._checar_totais(cliente_id, corrigir)
        problemas += self._checar_extrato(cliente_id, corrigir)

        self.stdout.write("\n" + "=" * 60)
        if problemas == 0:
            self.stdout.write(self.style.SUCCESS("Tudo certo. Nenhuma inconsistência encontrada."))
        else:
            estilo = self.style.WARNING if corrigir else self.style.ERROR
            self.stdout.write(estilo(f"{problemas} inconsistência(s) encontrada(s)."))
            if not corrigir:
                self.stdout.write("Rode novamente com --corrigir para tratar as que são automáticas.")

    # ────────────────────────────────────────────────────────────────────

    def _checar_vendas_orfas(self, cliente_id) -> int:
        """Movimentos de VENDA no ledger que não viraram lote de venda."""
        movimentos = AnimalMovement.objects.filter(operation_type='VENDA')
        if cliente_id:
            movimentos = movimentos.filter(client_id=cliente_id)

        importados = set(
            SaleItem.objects.filter(movement__isnull=False)
            .values_list('movement_id', flat=True)
        )
        orfaos = [m for m in movimentos.only('id') if m.id not in importados]

        self.stdout.write("\n1. Movimentações de venda sem lote vinculado")
        if not orfaos:
            self.stdout.write(self.style.SUCCESS("   OK — todas as vendas do ledger foram importadas."))
            return 0

        self.stdout.write(self.style.ERROR(f"   {len(orfaos)} movimentação(ões) fora do financeiro:"))
        for m in orfaos[:10]:
            self.stdout.write(f"     - {m.id}")
        if len(orfaos) > 10:
            self.stdout.write(f"     ... e mais {len(orfaos) - 10}")
        self.stdout.write(
            "   Correção: rode a migração de backfill novamente "
            "(ela é idempotente e só importa o que falta)."
        )
        return len(orfaos)

    def _checar_lotes_sem_movimentacao(self, cliente_id) -> int:
        """Lotes apontando para movimentação inexistente (não deveria ocorrer)."""
        itens = SaleItem.objects.filter(movement__isnull=True).select_related('sale')
        if cliente_id:
            itens = itens.filter(sale__client_id=cliente_id)
        total = itens.count()

        self.stdout.write("\n2. Lotes sem movimentação de estoque")
        if total == 0:
            self.stdout.write(self.style.SUCCESS("   OK — todos os lotes têm baixa de estoque."))
            return 0

        self.stdout.write(self.style.ERROR(f"   {total} lote(s) sem movimentação:"))
        for item in itens[:10]:
            self.stdout.write(f"     - lote {item.id} da venda {item.sale_id}")
        return total

    def _checar_totais(self, cliente_id, corrigir) -> int:
        """Totais em cache da venda contra a soma real dos lotes."""
        vendas = Sale.objects.prefetch_related('items')
        if cliente_id:
            vendas = vendas.filter(client_id=cliente_id)

        divergentes = []
        for venda in vendas.iterator(chunk_size=500):
            qtd = 0
            peso = None
            valor = None
            for item in venda.items.all():
                qtd += item.quantity
                if item.total_weight is not None:
                    peso = (peso or ZERO) + item.total_weight
                if item.total_amount is not None:
                    valor = (valor or ZERO) + item.total_amount
            valor = quantize_money(valor)

            if (venda.total_quantity, venda.total_weight, venda.total_amount) != (qtd, peso, valor):
                divergentes.append((venda, qtd, peso, valor))

        self.stdout.write("\n3. Totais das vendas")
        if not divergentes:
            self.stdout.write(self.style.SUCCESS("   OK — todos os totais batem com os lotes."))
            return 0

        self.stdout.write(self.style.ERROR(f"   {len(divergentes)} venda(s) com total divergente:"))
        for venda, qtd, peso, valor in divergentes[:10]:
            self.stdout.write(
                f"     - {venda.id}: gravado R$ {venda.total_amount} / "
                f"calculado R$ {valor}"
            )

        if corrigir:
            with transaction.atomic():
                for venda, qtd, peso, valor in divergentes:
                    venda.total_quantity = qtd
                    venda.total_weight = peso
                    venda.total_amount = valor
                    venda.save(update_fields=[
                        'total_quantity', 'total_weight', 'total_amount', 'updated_at',
                    ])
            self.stdout.write(self.style.SUCCESS(f"   Corrigidas {len(divergentes)} venda(s)."))
        return len(divergentes)

    def _checar_extrato(self, cliente_id, corrigir) -> int:
        """Lançamentos do extrato contra as vendas e pagamentos de origem."""
        problemas = 0

        # ── Vendas ativas com valor devem ter exatamente um débito igual ──
        vendas = Sale.objects.filter(status=SaleStatus.ATIVA).annotate(
            n_lancamentos=Count('entries'),
            soma_lancamentos=Sum('entries__amount'),
        )
        if cliente_id:
            vendas = vendas.filter(client_id=cliente_id)

        vendas_ruins = []
        for venda in vendas.iterator(chunk_size=500):
            esperado = venda.total_amount if (venda.total_amount or ZERO) > ZERO else None
            if esperado is None:
                if venda.n_lancamentos != 0:
                    vendas_ruins.append((venda, "tem lançamento mas a venda está sem valor"))
            elif venda.n_lancamentos != 1:
                vendas_ruins.append((venda, f"tem {venda.n_lancamentos} lançamentos, esperado 1"))
            elif venda.soma_lancamentos != esperado:
                vendas_ruins.append((
                    venda, f"lançamento de R$ {venda.soma_lancamentos}, esperado R$ {esperado}"
                ))

        # ── Pagamentos devem ter exatamente um crédito igual ──────────────
        pagamentos = Payment.objects.annotate(
            n_lancamentos=Count('entries'),
            soma_lancamentos=Sum('entries__amount'),
        )
        if cliente_id:
            pagamentos = pagamentos.filter(client_id=cliente_id)

        pagamentos_ruins = [
            p for p in pagamentos.iterator(chunk_size=500)
            if p.n_lancamentos != 1 or p.soma_lancamentos != p.amount
        ]

        # ── Vendas canceladas não podem ter lançamento ────────────────────
        canceladas_com_lancamento = Sale.objects.filter(
            status=SaleStatus.CANCELADA, entries__isnull=False,
        ).distinct()
        if cliente_id:
            canceladas_com_lancamento = canceladas_com_lancamento.filter(client_id=cliente_id)
        canceladas_ruins = list(canceladas_com_lancamento)

        self.stdout.write("\n4. Extrato dos clientes")
        total = len(vendas_ruins) + len(pagamentos_ruins) + len(canceladas_ruins)
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "   OK — extrato coerente com vendas e pagamentos."
            ))
            return 0

        for venda, motivo in vendas_ruins[:10]:
            self.stdout.write(self.style.ERROR(f"     - venda {venda.id}: {motivo}"))
        for p in pagamentos_ruins[:10]:
            self.stdout.write(self.style.ERROR(
                f"     - pagamento {p.id}: {p.n_lancamentos} lançamento(s), "
                f"soma R$ {p.soma_lancamentos}, esperado R$ {p.amount}"
            ))
        for s in canceladas_ruins[:10]:
            self.stdout.write(self.style.ERROR(
                f"     - venda cancelada {s.id} ainda tem lançamento no extrato"
            ))

        if corrigir:
            with transaction.atomic():
                for venda, _motivo in vendas_ruins:
                    self._refazer_lancamento_venda(venda)
                for p in pagamentos_ruins:
                    self._refazer_lancamento_pagamento(p)
                for s in canceladas_ruins:
                    s.entries.all().delete()
            self.stdout.write(self.style.SUCCESS(f"   Corrigidos {total} caso(s)."))

        problemas += total
        return problemas

    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def _refazer_lancamento_venda(venda):
        venda.entries.all().delete()
        if venda.status != SaleStatus.ATIVA:
            return
        if (venda.total_amount or ZERO) <= ZERO:
            return
        FinancialEntry.objects.create(
            client_id=venda.client_id,
            date=venda.date,
            entry_type=EntryType.DEBITO,
            amount=venda.total_amount,
            source_type=EntrySource.VENDA,
            sale=venda,
            description=f"Venda de {venda.total_quantity} animal(is)",
            created_by_id=venda.created_by_id,
        )

    @staticmethod
    def _refazer_lancamento_pagamento(pagamento):
        pagamento.entries.all().delete()
        FinancialEntry.objects.create(
            client_id=pagamento.client_id,
            date=pagamento.date,
            entry_type=EntryType.CREDITO,
            amount=pagamento.amount,
            source_type=EntrySource.PAGAMENTO,
            payment=pagamento,
            description=pagamento.description or pagamento.get_payment_type_display(),
            created_by_id=pagamento.created_by_id,
        )

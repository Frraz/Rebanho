"""
operations/services/occurrence_service.py
══════════════════════════════════════════

Service responsável pelo cancelamento (estorno) e edição de ocorrências.

DESIGN:
- AnimalMovement é imutável (ledger pattern) — nunca tocamos nele diretamente
- O cancelamento cria um AnimalMovementCancellation (evento separado)
- O saldo é devolvido via FarmStockBalance.current_quantity += quantidade
- Toda a operação é atômica (transaction.atomic + select_for_update)

IMPORTANTE — select_for_update() + PostgreSQL:
- NÃO combinar com select_related() de FKs nullable (client, death_reason)
- Isso gera LEFT OUTER JOIN que o PostgreSQL rejeita com FOR UPDATE
- AnimalMovement é buscado sem select_related
- FarmStockBalance não tem FKs nullable, select_related seguro ali
"""
import logging

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


class OccurrenceService:
    """
    Serviço de domínio para operações sobre ocorrências.
    Regras de negócio encapsuladas aqui, nunca nas views.
    """

    CANCELLABLE_TYPES = frozenset({'MORTE', 'ABATE', 'VENDA', 'DOACAO'})

    # Campos que NUNCA podem ser alterados via edit_occurrence.
    _BLOCKED_EDIT_FIELDS = frozenset({'farm_stock_balance', 'farm_stock_balance_id',
                                       'operation_type', 'id'})

    # ────────────────────────────────────────────────────────────────────
    # CANCELAMENTO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def cancel_occurrence(movement_id: str, cancelled_by, notes: str = '') -> dict:
        """
        Estorna uma ocorrência, devolvendo o saldo ao estoque da fazenda.

        Args:
            movement_id: UUID (string) do AnimalMovement
            cancelled_by: instância do User
            notes: observação opcional sobre o motivo do cancelamento

        Returns:
            dict com dados do estorno realizado

        Raises:
            ValidationError: se já cancelada, tipo inválido ou não encontrada
        """
        from inventory.models import (
            AnimalMovement,
            AnimalMovementCancellation,
            FarmStockBalance,
        )

        # ── 1. Buscar o movement com lock
        # SEM select_related: client e death_reason são FKs nullable e
        # geram LEFT OUTER JOIN — incompatível com FOR UPDATE no PostgreSQL.
        try:
            movement = (
                AnimalMovement.objects
                .select_for_update(nowait=False)
                .get(id=movement_id)
            )
        except AnimalMovement.DoesNotExist:
            raise ValidationError("Ocorrência não encontrada.")

        # ── 2. Verificar se já foi cancelada
        # Usamos query direta em vez de hasattr(): mais explícito e
        # não depende do cache de atributo do ORM após select_for_update.
        try:
            c = (
                AnimalMovementCancellation.objects
                .select_related('cancelled_by')
                .get(movement_id=movement_id)
            )
            raise ValidationError(
                f"Esta ocorrência já foi cancelada em "
                f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                f"por {c.cancelled_by.get_full_name() or c.cancelled_by.username}."
            )
        except AnimalMovementCancellation.DoesNotExist:
            pass  # ainda não cancelada — prosseguir

        # ── 3. Validar tipo cancelável
        if movement.operation_type not in OccurrenceService.CANCELLABLE_TYPES:
            raise ValidationError(
                f"Operações do tipo '{movement.get_operation_type_display()}' "
                f"não podem ser canceladas por este método."
            )

        # ── 4. Buscar o saldo com lock
        # FarmStockBalance só tem FKs NOT NULL, select_related é seguro aqui.
        balance = (
            FarmStockBalance.objects
            .select_related('farm', 'animal_category')
            .select_for_update(nowait=False)
            .get(id=movement.farm_stock_balance_id)
        )

        # ── 5. Capturar dados antes de alterar
        farm_name = balance.farm.name
        farm_id = str(balance.farm_id)
        category_name = balance.animal_category.name
        quantity = movement.quantity
        balance_before = balance.current_quantity

        # ── 6. Estornar o saldo (ocorrência era SAÍDA → somamos de volta)
        balance.current_quantity += quantity
        balance.save(update_fields=['current_quantity'])
        balance_after = balance.current_quantity

        # ── 7. Registrar o cancelamento (evento separado, auditável)
        AnimalMovementCancellation.objects.create(
            movement=movement,
            cancelled_by=cancelled_by,
            quantity_restored=quantity,
            balance_before=balance_before,
            balance_after=balance_after,
            notes=notes,
        )

        # ── 8. Invalidar cache da fazenda
        # farm_detail_view usa cache de 5min. Sem isso, o saldo
        # só seria atualizado na tela após o cache expirar naturalmente.
        OccurrenceService._invalidate_farm_cache(farm_id)

        logger.warning(
            "[CANCELAMENTO] Ocorrência %s estornada. "
            "Fazenda: %s | Categoria: %s | "
            "Quantidade: +%s | "
            "Saldo: %s → %s | "
            "Cancelado por: %s",
            movement_id, farm_name, category_name,
            quantity, balance_before, balance_after,
            cancelled_by.username,
        )

        return {
            'farm': farm_name,
            'farm_id': farm_id,
            'category': category_name,
            'operation_type': movement.operation_type,
            'operation_display': movement.get_operation_type_display(),
            'quantity_restored': quantity,
            'balance_before': balance_before,
            'balance_after': balance_after,
        }

    # ────────────────────────────────────────────────────────────────────
    # EDIÇÃO
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def edit_occurrence(movement_id: str, updated_by, data: dict) -> dict:
        """
        Edita campos de uma ocorrência ativa (não cancelada).

        DESIGN INTENCIONAL — bypass do model.save():
        O AnimalMovement.save() proíbe UPDATEs via proteção de ledger.
        Aqui usamos QuerySet.update() de forma DELIBERADA e CONTROLADA,
        pois este service é o único ponto autorizado a fazer isso.
        O campo metadata registra auditoria da edição (_edited_by, _edited_at).

        Campos editáveis:
          - quantity        → recalcula delta no FarmStockBalance com select_for_update
          - timestamp       → sem impacto no saldo
          - metadata        → merge seguro (preserva chaves existentes)
          - client_id       → sem impacto no saldo
          - death_reason_id → sem impacto no saldo

        Campos BLOQUEADOS (raises ValidationError):
          - farm_stock_balance → trocaria de saldo, inviável
          - operation_type     → alteraria semântica da operação

        Args:
            movement_id: UUID da ocorrência
            updated_by:  User que está editando
            data: dict com subset dos campos editáveis:
                quantity (int), timestamp (datetime),
                metadata (dict — merge), client_id (str UUID),
                death_reason_id (str UUID)

        Returns:
            dict com resultado da edição para feedback na view

        Raises:
            ValidationError: ocorrência cancelada, tipo inválido,
                             saldo insuficiente para delta positivo,
                             campo bloqueado presente em data
        """
        from inventory.models import (
            AnimalMovement,
            AnimalMovementCancellation,
            FarmStockBalance,
        )

        # ── 0. Rejeitar campos proibidos ANTES de qualquer query
        blocked = OccurrenceService._BLOCKED_EDIT_FIELDS & data.keys()
        if blocked:
            raise ValidationError(
                f"Os seguintes campos não podem ser editados: {', '.join(sorted(blocked))}."
            )

        # ── 1. Buscar o movement COM lock para evitar lost update
        # SEM select_related: client e death_reason são FKs nullable —
        # LEFT OUTER JOIN é incompatível com FOR UPDATE no PostgreSQL.
        try:
            movement = (
                AnimalMovement.objects
                .select_for_update(nowait=False)
                .get(id=movement_id)
            )
        except AnimalMovement.DoesNotExist:
            raise ValidationError("Ocorrência não encontrada.")

        # ── 2. Bloquear edição de ocorrências canceladas
        if AnimalMovementCancellation.objects.filter(movement_id=movement_id).exists():
            raise ValidationError("Ocorrências canceladas não podem ser editadas.")

        # ── 3. Validar tipo editável
        if movement.operation_type not in OccurrenceService.CANCELLABLE_TYPES:
            raise ValidationError(
                f"Operações do tipo '{movement.get_operation_type_display()}' "
                "não podem ser editadas por este método."
            )

        # ── 4. Campos a atualizar no movement (via QuerySet.update — bypass intencional)
        update_fields = {}
        balance_result = None

        # ── 5. Processar delta de quantidade (requer lock no FarmStockBalance)
        new_quantity = data.get('quantity')
        if new_quantity is not None and new_quantity != movement.quantity:
            if new_quantity <= 0:
                raise ValidationError("Quantidade deve ser maior que zero.")

            # Lock pessimista APENAS no FarmStockBalance (sem FKs nullable → seguro)
            balance = (
                FarmStockBalance.objects
                .select_related('farm', 'animal_category')
                .select_for_update(nowait=False)
                .get(id=movement.farm_stock_balance_id)
            )

            delta = new_quantity - movement.quantity  # positivo = saída maior
            balance_before = balance.current_quantity

            if delta > 0:
                # Saída aumentou → precisamos retirar mais do saldo
                if balance.current_quantity < delta:
                    raise ValidationError(
                        f"Saldo insuficiente para aumentar a quantidade. "
                        f"Disponível: {balance.current_quantity}, delta necessário: {delta}."
                    )
                new_balance = balance.current_quantity - delta
            else:
                # Saída diminuiu → devolvemos a diferença ao saldo
                new_balance = balance.current_quantity + abs(delta)

            updated_rows = FarmStockBalance.objects.filter(
                id=balance.id,
                version=balance.version,
            ).update(
                current_quantity=new_balance,
                version=F('version') + 1,
                updated_at=timezone.now(),
            )

            if updated_rows == 0:
                raise ValidationError(
                    "Conflito de concorrência ao atualizar saldo. Tente novamente."
                )

            update_fields['quantity'] = new_quantity
            balance_result = {
                'before': balance_before,
                'after': new_balance,
            }

        # ── 6. Campos sem impacto no saldo
        if 'timestamp' in data and data['timestamp']:
            update_fields['timestamp'] = data['timestamp']

        if 'client_id' in data:
            update_fields['client_id'] = data['client_id'] or None

        if 'death_reason_id' in data:
            update_fields['death_reason_id'] = data['death_reason_id'] or None

        # ── 7. Se não há nada para atualizar, retornar cedo (sem update vazio)
        if not update_fields and 'metadata' not in data:
            return {
                'farm': self._get_farm_name(movement),
                'category': self._get_category_name(movement),
                'operation_display': movement.get_operation_type_display(),
                'quantity_before': movement.quantity,
                'quantity_after': movement.quantity,
                'balance': None,
                'changed_fields': [],
            }

        # ── 8. Merge de metadata com auditoria de edição
        current_meta = movement.metadata or {}
        if 'metadata' in data and isinstance(data['metadata'], dict):
            current_meta.update({k: v for k, v in data['metadata'].items() if v is not None})

        # Trilha de auditoria sempre gravada quando há mudança
        current_meta['_edited_by'] = updated_by.username
        current_meta['_edited_at'] = timezone.now().isoformat()
        if 'quantity' in update_fields:
            current_meta['_qty_before_edit'] = movement.quantity
        update_fields['metadata'] = current_meta

        # ── 9. Aplicar update — bypass INTENCIONAL do model.save()
        AnimalMovement.objects.filter(id=movement_id).update(**update_fields)

        # ── 10. Invalidar cache
        farm_id = str(movement.farm_stock_balance_id)
        # Precisamos do farm_id real — buscar via FarmStockBalance
        # (movement foi obtido sem select_related)
        try:
            farm_id = str(
                FarmStockBalance.objects
                .values_list('farm_id', flat=True)
                .get(id=movement.farm_stock_balance_id)
            )
        except FarmStockBalance.DoesNotExist:
            farm_id = None

        if farm_id:
            OccurrenceService._invalidate_farm_cache(farm_id)

        # ── 11. Buscar nomes para o retorno (query leve, sem lock)
        farm_name = ''
        category_name = ''
        if farm_id:
            try:
                fsb = (
                    FarmStockBalance.objects
                    .select_related('farm', 'animal_category')
                    .get(id=movement.farm_stock_balance_id)
                )
                farm_name = fsb.farm.name
                category_name = fsb.animal_category.name
            except FarmStockBalance.DoesNotExist:
                pass

        logger.warning(
            "[EDIÇÃO] Ocorrência %s editada por %s. "
            "Campos: %s | Qty: %s → %s",
            movement_id, updated_by.username,
            list(update_fields.keys()),
            movement.quantity,
            update_fields.get('quantity', movement.quantity),
        )

        return {
            'farm': farm_name,
            'category': category_name,
            'operation_display': movement.get_operation_type_display(),
            'quantity_before': movement.quantity,
            'quantity_after': update_fields.get('quantity', movement.quantity),
            'balance': balance_result,
            'changed_fields': list(update_fields.keys()),
        }

    # ────────────────────────────────────────────────────────────────────
    # HELPERS PRIVADOS
    # ────────────────────────────────────────────────────────────────────

    @staticmethod
    def _invalidate_farm_cache(farm_id: str) -> None:
        """Invalida todas as chaves de cache conhecidas para uma fazenda."""
        cache.delete(f'farm_summary_{farm_id}')
        cache.delete(f'farm_history_{farm_id}')
        cache.delete(f'farm_stock_{farm_id}')
        cache.delete('farms_list')
"""
operations/services/occurrence_service.py
══════════════════════════════════════════

Service responsável pelo cancelamento (estorno) de ocorrências.

DESIGN:
- AnimalMovement é imutável (ledger pattern) — nunca tocamos nele
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
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class OccurrenceService:
    """
    Serviço de domínio para operações sobre ocorrências.
    Regras de negócio encapsuladas aqui, nunca nas views.
    """

    CANCELLABLE_TYPES = frozenset({'MORTE', 'ABATE', 'VENDA', 'DOACAO'})

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
        from inventory.models import AnimalMovement, FarmStockBalance
        from inventory.models import AnimalMovementCancellation

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
        category_name = balance.animal_category.name
        quantity = movement.quantity
        balance_before = balance.current_quantity       # ← campo correto

        # ── 6. Estornar o saldo (ocorrência era SAÍDA → somamos de volta)
        balance.current_quantity += quantity            # ← campo correto
        balance.save(update_fields=['current_quantity'])  # ← campo correto
        balance_after = balance.current_quantity        # ← campo correto

        # ── 7. Registrar o cancelamento (evento separado, auditável)
        AnimalMovementCancellation.objects.create(
            movement=movement,
            cancelled_by=cancelled_by,
            quantity_restored=quantity,
            balance_before=balance_before,
            balance_after=balance_after,
            notes=notes,
        )

        logger.warning(
            f"[CANCELAMENTO] Ocorrência {movement_id} estornada. "
            f"Fazenda: {farm_name} | Categoria: {category_name} | "
            f"Quantidade: +{quantity} | "
            f"Saldo: {balance_before} → {balance_after} | "
            f"Cancelado por: {cancelled_by.username}"
        )

        return {
            'farm': farm_name,
            'category': category_name,
            'operation_type': movement.operation_type,
            'operation_display': movement.get_operation_type_display(),
            'quantity_restored': quantity,
            'balance_before': balance_before,
            'balance_after': balance_after,
        }
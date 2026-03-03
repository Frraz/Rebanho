"""
Movement Service - Serviço de Movimentações.

Este é o CORAÇÃO do sistema de inventário.

Responsável por:
- Registrar entradas (NASCIMENTO, COMPRA, DESMAME, etc.)
- Registrar saídas (MORTE, VENDA, ABATE, DOAÇÃO)
- Cancelar/estornar movimentações
- Editar movimentações ativas (com auditoria no metadata)
- Garantir integridade de saldo (nunca negativo)
- Manter consistência entre ledger e snapshot
- Controle de concorrência

IMPORTANTE: TODA operação que altera saldo DEVE passar por este service.
"""
import logging
from typing import Optional, Dict, Any

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from farms.models import Farm
from inventory.domain import (
    OperationType,
    MovementType,
    validate_positive_quantity,
    validate_sufficient_stock,
    validate_operation_requirements,
    InsufficientStockError,
    StockBalanceNotFoundError,
    ConcurrencyError,
)
from inventory.models import (
    AnimalMovement,
    AnimalMovementCancellation,
    FarmStockBalance,
)
from operations.models import Client, DeathReason

logger = logging.getLogger(__name__)

# Tipos de operação compostas (envolvem dois registros simultâneos).
# Quantidade NÃO pode ser editada nesses tipos — cancelar e refazer.
COMPOSITE_OPERATION_TYPES = frozenset({
    OperationType.MANEJO_IN.value,
    OperationType.MANEJO_OUT.value,
    OperationType.MUDANCA_CATEGORIA_IN.value,
    OperationType.MUDANCA_CATEGORIA_OUT.value,
    OperationType.DESMAME_IN.value,
    OperationType.DESMAME_OUT.value,
})


class MovementService:
    """
    Serviço de Movimentações de Animais.

    Implementa o padrão Ledger + Snapshot com garantias ACID.
    """

    @staticmethod
    @transaction.atomic
    def execute_entrada(
        farm_id: str,
        animal_category_id: str,
        operation_type: OperationType,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> AnimalMovement:
        """
        Executa uma operação de ENTRADA (aumenta saldo).

        Operações permitidas:
        - NASCIMENTO, COMPRA, DESMAME_IN, SALDO
        - MANEJO_IN, MUDANCA_CATEGORIA_IN (usado internamente)
        """
        # 1. Validações de domínio
        validate_positive_quantity(quantity)

        expected_movement_type = operation_type.get_movement_type()
        if expected_movement_type != MovementType.ENTRADA:
            raise ValueError(
                f"Operação '{operation_type.value}' não é de ENTRADA. "
                f"Use execute_saida() para operações de saída."
            )

        # 2. Obter saldo com lock pessimista
        try:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                farm_id=farm_id,
                animal_category_id=animal_category_id,
            )
        except FarmStockBalance.DoesNotExist:
            farm = Farm.objects.get(id=farm_id)
            from inventory.models import AnimalCategory
            category = AnimalCategory.objects.get(id=animal_category_id)
            raise StockBalanceNotFoundError(farm.name, category.name)

        # 3. Calcular novo saldo
        new_quantity = stock_balance.current_quantity + quantity

        # 4. Criar registro no ledger
        movement = AnimalMovement.objects.create(
            farm_stock_balance=stock_balance,
            movement_type=MovementType.ENTRADA.value,
            operation_type=operation_type.value,
            quantity=quantity,
            timestamp=timestamp or timezone.now(),
            metadata=metadata or {},
            created_by=user,
            ip_address=ip_address,
        )

        # 5. Atualizar saldo com optimistic locking
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version,
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now(),
        )

        if updated_rows == 0:
            raise ConcurrencyError("Saldo de estoque")

        return movement

    @staticmethod
    @transaction.atomic
    def execute_saida(
        farm_id: str,
        animal_category_id: str,
        operation_type: OperationType,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        client_id: Optional[str] = None,
        death_reason_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AnimalMovement:
        """
        Executa uma operação de SAÍDA (diminui saldo).

        Operações permitidas:
        - MORTE (requer death_reason_id), VENDA (requer client_id)
        - ABATE, DOACAO (requer client_id)
        - MANEJO_OUT, MUDANCA_CATEGORIA_OUT, DESMAME_OUT (interno)
        """
        # 1. Validações de domínio
        validate_positive_quantity(quantity)
        validate_operation_requirements(
            operation_type=operation_type,
            client_id=client_id,
            death_reason_id=death_reason_id,
        )

        expected_movement_type = operation_type.get_movement_type()
        if expected_movement_type != MovementType.SAIDA:
            raise ValueError(
                f"Operação '{operation_type.value}' não é de SAÍDA. "
                f"Use execute_entrada() para operações de entrada."
            )

        # 2. Obter saldo com lock pessimista
        try:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                farm_id=farm_id,
                animal_category_id=animal_category_id,
            )
        except FarmStockBalance.DoesNotExist:
            farm = Farm.objects.get(id=farm_id)
            from inventory.models import AnimalCategory
            category = AnimalCategory.objects.get(id=animal_category_id)
            raise StockBalanceNotFoundError(farm.name, category.name)

        # 3. Validar saldo suficiente
        validate_sufficient_stock(
            current_stock=stock_balance.current_quantity,
            requested_quantity=quantity,
            farm_name=stock_balance.farm.name,
            category_name=stock_balance.animal_category.name,
        )

        # 4. Calcular novo saldo
        new_quantity = stock_balance.current_quantity - quantity
        if new_quantity < 0:
            raise InsufficientStockError(
                farm_name=stock_balance.farm.name,
                category_name=stock_balance.animal_category.name,
                requested=quantity,
                available=stock_balance.current_quantity,
            )

        # 5. Obter relacionamentos opcionais
        client = Client.objects.get(id=client_id) if client_id else None
        death_reason = DeathReason.objects.get(id=death_reason_id) if death_reason_id else None

        # 6. Criar registro no ledger
        movement = AnimalMovement.objects.create(
            farm_stock_balance=stock_balance,
            movement_type=MovementType.SAIDA.value,
            operation_type=operation_type.value,
            quantity=quantity,
            timestamp=timestamp or timezone.now(),
            client=client,
            death_reason=death_reason,
            metadata=metadata or {},
            created_by=user,
            ip_address=ip_address,
        )

        # 7. Atualizar saldo com optimistic locking
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version,
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now(),
        )

        if updated_rows == 0:
            raise ConcurrencyError("Saldo de estoque")

        return movement

    @staticmethod
    @transaction.atomic
    def cancel_movement(
        movement_id: str,
        cancelled_by,
        notes: str = '',
    ) -> dict:
        """
        Cancela (estorna) uma movimentação, revertendo seu efeito no saldo.

        - ENTRADA → estorno diminui o saldo
        - SAÍDA   → estorno aumenta o saldo
        - Operações compostas cancelam ambos os lados atomicamente
        - Ledger permanece imutável (cria AnimalMovementCancellation)

        ATENÇÃO: select_for_update() NÃO é usado no fetch inicial porque
        FKs nullable geram LEFT OUTER JOINs incompatíveis com FOR UPDATE
        no PostgreSQL. Lock é aplicado apenas no FarmStockBalance.
        """
        # Etapa 1: Fetch SEM lock (relações nullable)
        movement = (
            AnimalMovement.objects
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
            )
            .prefetch_related(
                'cancellation',
                'cancellation__cancelled_by',
            )
            .get(pk=movement_id)
        )

        # Verificar se já foi cancelada
        try:
            c = movement.cancellation
            raise ValidationError(
                f"Esta movimentação já foi cancelada em "
                f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                f"por {c.cancelled_by.username}."
            )
        except AnimalMovementCancellation.DoesNotExist:
            pass

        # Buscar lado relacionado (operações compostas)
        related_movement = None
        if movement.related_movement_id:
            related_movement = (
                AnimalMovement.objects
                .select_related(
                    'farm_stock_balance__farm',
                    'farm_stock_balance__animal_category',
                )
                .prefetch_related('cancellation', 'cancellation__cancelled_by')
                .get(pk=movement.related_movement_id)
            )
            try:
                rc = related_movement.cancellation
                raise ValidationError(
                    f"O movimento relacionado desta operação já foi cancelado em "
                    f"{rc.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                    f"por {rc.cancelled_by.username}."
                )
            except AnimalMovementCancellation.DoesNotExist:
                pass

        # Etapa 2: Lock + atualização de saldo
        movements_to_cancel = [movement]
        if related_movement:
            movements_to_cancel.append(related_movement)

        cancellations_created = []

        for mov in movements_to_cancel:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                pk=mov.farm_stock_balance_id,
            )

            balance_before = stock_balance.current_quantity

            if mov.movement_type == 'ENTRADA':
                if balance_before < mov.quantity:
                    raise InsufficientStockError(
                        farm_name=stock_balance.farm.name,
                        category_name=stock_balance.animal_category.name,
                        requested=mov.quantity,
                        available=balance_before,
                    )
                new_quantity = balance_before - mov.quantity
            else:
                new_quantity = balance_before + mov.quantity

            updated_rows = FarmStockBalance.objects.filter(
                id=stock_balance.id,
                version=stock_balance.version,
            ).update(
                current_quantity=new_quantity,
                version=F('version') + 1,
                updated_at=timezone.now(),
            )

            if updated_rows == 0:
                raise ConcurrencyError("Saldo de estoque")

            cancellation = AnimalMovementCancellation.objects.create(
                movement=mov,
                cancelled_by=cancelled_by,
                quantity_restored=mov.quantity,
                balance_before=balance_before,
                balance_after=new_quantity,
                notes=notes,
            )
            cancellations_created.append(cancellation)

        main_cancellation = cancellations_created[0]
        return {
            'movement_id': str(movement.id),
            'operation_display': movement.get_operation_type_display(),
            'farm': movement.farm_stock_balance.farm.name,
            'category': movement.farm_stock_balance.animal_category.name,
            'quantity_restored': movement.quantity,
            'balance_before': main_cancellation.balance_before,
            'balance_after': main_cancellation.balance_after,
            'is_composite': len(movements_to_cancel) > 1,
        }

    @staticmethod
    def get_operation_summary(movement: AnimalMovement) -> Dict[str, Any]:
        """Retorna um resumo legível da operação."""
        return {
            'id': str(movement.id),
            'fazenda': movement.farm_stock_balance.farm.name,
            'categoria': movement.farm_stock_balance.animal_category.name,
            'tipo_movimento': movement.get_movement_type_display(),
            'operacao': movement.get_operation_type_display(),
            'quantidade': movement.quantity,
            'data': movement.timestamp.strftime('%d/%m/%Y %H:%M'),
            'usuario': movement.created_by.username,
            'metadata': movement.metadata,
        }

    @staticmethod
    @transaction.atomic
    def edit_movement(movement_id: str, updated_by, data: dict) -> dict:
        """
        Edita campos de uma movimentação ativa (não cancelada).

        REGRAS:
        - Operações simples (NASCIMENTO, COMPRA, SALDO): todos os campos editáveis
        - Operações compostas (MANEJO, DESMAME, MUDANCA_CATEGORIA):
            → quantidade BLOQUEADA
            → timestamp e metadata editáveis

        DESIGN: usa QuerySet.update() deliberadamente para bypassar a
        proteção de ledger do model.save(). Auditoria via metadata.

        Args:
            movement_id: UUID da movimentação
            updated_by:  User que está editando
            data: dict com campos editáveis:
                quantity (int), timestamp (datetime), metadata (dict)

        Returns:
            dict com resultado para feedback na view

        Raises:
            ValidationError: cancelada, saldo insuficiente, qty em composta
        """
        # 1. Buscar movement SEM lock (FKs nullable)
        try:
            movement = (
                AnimalMovement.objects
                .select_related(
                    'farm_stock_balance__farm',
                    'farm_stock_balance__animal_category',
                )
                .get(id=movement_id)
            )
        except AnimalMovement.DoesNotExist:
            raise ValidationError("Movimentação não encontrada.")

        # 2. Bloquear edição de movimentos cancelados
        if AnimalMovementCancellation.objects.filter(movement_id=movement_id).exists():
            raise ValidationError("Movimentações canceladas não podem ser editadas.")

        # 3. Determinar se é operação composta
        is_composite = movement.operation_type in COMPOSITE_OPERATION_TYPES

        # 4. Verificar se quantidade está sendo alterada
        new_quantity = data.get('quantity')
        quantity_changed = (
            new_quantity is not None
            and int(new_quantity) != movement.quantity
        )

        if quantity_changed and is_composite:
            raise ValidationError(
                "Não é possível editar a quantidade de operações compostas "
                "(Manejo, Desmame, Mudança de Categoria). "
                "Para corrigir, cancele a operação e registre novamente."
            )

        update_fields = {}
        balance_result = None
        old_quantity = movement.quantity

        # 5. Delta de quantidade (apenas operações simples)
        if quantity_changed:
            new_quantity = int(new_quantity)
            if new_quantity <= 0:
                raise ValidationError("Quantidade deve ser maior que zero.")

            balance = (
                FarmStockBalance.objects
                .select_for_update(nowait=False)
                .get(id=movement.farm_stock_balance_id)
            )

            balance_before = balance.current_quantity
            delta = new_quantity - old_quantity

            if movement.movement_type == MovementType.ENTRADA.value:
                new_balance = balance_before + delta
                if new_balance < 0:
                    raise ValidationError(
                        f"Não é possível reduzir esta entrada: "
                        f"o saldo atual ({balance_before}) ficaria negativo."
                    )
            else:
                new_balance = balance_before - delta
                if new_balance < 0:
                    raise ValidationError(
                        f"Saldo insuficiente para aumentar a saída. "
                        f"Disponível: {balance_before}, delta: {delta}."
                    )

            updated_rows = FarmStockBalance.objects.filter(
                id=balance.id,
                version=balance.version,
            ).update(
                current_quantity=new_balance,
                version=F('version') + 1,
                updated_at=timezone.now(),
            )

            if updated_rows == 0:
                raise ConcurrencyError("Saldo de estoque")

            update_fields['quantity'] = new_quantity
            balance_result = {'before': balance_before, 'after': new_balance}

        # 6. Campos sem impacto no saldo
        if 'timestamp' in data and data['timestamp']:
            update_fields['timestamp'] = data['timestamp']

        # 7. Merge de metadata + trilha de auditoria
        if 'metadata' in data or update_fields:
            current_meta = dict(movement.metadata or {})
            if 'metadata' in data:
                current_meta.update({
                    k: v for k, v in data['metadata'].items()
                    if v is not None
                })

            # Trilha de auditoria — sempre gravada em qualquer edição
            edit_count = current_meta.get('_edit_count', 0)
            current_meta['_edited_by'] = updated_by.username
            current_meta['_edited_at'] = timezone.now().isoformat()
            current_meta['_qty_before_edit'] = old_quantity
            current_meta['_edit_count'] = edit_count + 1

            # Preservar quantidade original (primeira edição)
            if '_original_quantity' not in current_meta:
                current_meta['_original_quantity'] = old_quantity

            update_fields['metadata'] = current_meta

        # 8. Aplicar update — bypass INTENCIONAL do model.save()
        if update_fields:
            AnimalMovement.objects.filter(id=movement_id).update(**update_fields)

            # 9. Invalidar cache apenas se houve mudança efetiva
            farm_id = str(movement.farm_stock_balance.farm_id)
            cache.delete(f'farm_summary_{farm_id}')
            cache.delete(f'farm_history_{farm_id}')
            cache.delete('farms_list')

            logger.warning(
                "[EDIÇÃO] Movimentação %s editada por %s. "
                "Campos: %s | Qty: %s → %s",
                movement_id,
                updated_by.username,
                list(update_fields.keys()),
                old_quantity,
                update_fields.get('quantity', old_quantity),
            )

        return {
            'farm': movement.farm_stock_balance.farm.name,
            'category': movement.farm_stock_balance.animal_category.name,
            'operation_display': movement.get_operation_type_display(),
            'is_composite': is_composite,
            'quantity_before': old_quantity,
            'quantity_after': update_fields.get('quantity', old_quantity),
            'balance': balance_result,
        }
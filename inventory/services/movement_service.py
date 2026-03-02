"""
Movement Service - Serviço de Movimentações.

Este é o CORAÇÃO do sistema de inventário.

Responsável por:
- Registrar entradas (NASCIMENTO, COMPRA, DESMAME, etc.)
- Registrar saídas (MORTE, VENDA, ABATE, DOAÇÃO)
- Cancelar/estornar movimentações
- Garantir integridade de saldo (nunca negativo)
- Manter consistência entre ledger e snapshot
- Controle de concorrência

IMPORTANTE: TODA operação que altera saldo DEVE passar por este service.
"""
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from typing import Optional, Dict, Any

from inventory.models import FarmStockBalance, AnimalMovement
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
from farms.models import Farm
from operations.models import Client, DeathReason


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
        - NASCIMENTO
        - COMPRA
        - DESMAME
        - SALDO (ajuste positivo)
        - MANEJO_IN (usado internamente por TransferService)
        - MUDANCA_CATEGORIA_IN (usado internamente por TransferService)
        
        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            operation_type: Tipo de operação (OperationType)
            quantity: Quantidade de animais (deve ser > 0)
            user: Usuário que está registrando a operação
            timestamp: Data/hora da operação (default: agora)
            metadata: Dados adicionais em JSON (peso, observações, etc.)
            ip_address: IP de origem da requisição
            
        Returns:
            AnimalMovement: Registro criado no ledger
            
        Raises:
            InvalidQuantityError: Se quantidade <= 0
            StockBalanceNotFoundError: Se saldo não existir
            ConcurrencyError: Se houver conflito de versão
            InvalidOperationError: Se operação não for de entrada
        """
        
        # 1. VALIDAÇÕES DE DOMÍNIO
        validate_positive_quantity(quantity)
        
        # Verificar se a operação é realmente de ENTRADA
        expected_movement_type = operation_type.get_movement_type()
        if expected_movement_type != MovementType.ENTRADA:
            raise ValueError(
                f"Operação '{operation_type.value}' não é de ENTRADA. "
                f"Use execute_saida() para operações de saída."
            )
        
        # 2. OBTER SALDO COM LOCK PESSIMISTA (previne race condition)
        try:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                farm_id=farm_id,
                animal_category_id=animal_category_id
            )
        except FarmStockBalance.DoesNotExist:
            farm = Farm.objects.get(id=farm_id)
            from inventory.models import AnimalCategory
            category = AnimalCategory.objects.get(id=animal_category_id)
            raise StockBalanceNotFoundError(farm.name, category.name)
        
        # 3. CALCULAR NOVO SALDO
        new_quantity = stock_balance.current_quantity + quantity
        
        # 4. CRIAR REGISTRO NO LEDGER (imutável)
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
        
        # 5. ATUALIZAR SALDO CONSOLIDADO COM VERSIONING
        from django.db.models import F
        
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        
        # 6. VERIFICAR SE ATUALIZAÇÃO FOI BEM-SUCEDIDA
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
        - MORTE (requer death_reason_id)
        - VENDA (requer client_id)
        - ABATE
        - DOACAO (requer client_id)
        - MANEJO_OUT (usado internamente por TransferService)
        - MUDANCA_CATEGORIA_OUT (usado internamente por TransferService)
        
        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            operation_type: Tipo de operação (OperationType)
            quantity: Quantidade de animais (deve ser > 0)
            user: Usuário que está registrando a operação
            timestamp: Data/hora da operação (default: agora)
            metadata: Dados adicionais em JSON (peso, observações, etc.)
            client_id: UUID do cliente (obrigatório para VENDA e DOACAO)
            death_reason_id: UUID do motivo de morte (obrigatório para MORTE)
            ip_address: IP de origem da requisição
            
        Returns:
            AnimalMovement: Registro criado no ledger
            
        Raises:
            InvalidQuantityError: Se quantidade <= 0
            InsufficientStockError: Se saldo insuficiente
            StockBalanceNotFoundError: Se saldo não existir
            ConcurrencyError: Se houver conflito de versão
            InvalidOperationError: Se faltar dados obrigatórios
        """
        
        # 1. VALIDAÇÕES DE DOMÍNIO
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
        
        # 2. OBTER SALDO COM LOCK PESSIMISTA
        try:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                farm_id=farm_id,
                animal_category_id=animal_category_id
            )
        except FarmStockBalance.DoesNotExist:
            farm = Farm.objects.get(id=farm_id)
            from inventory.models import AnimalCategory
            category = AnimalCategory.objects.get(id=animal_category_id)
            raise StockBalanceNotFoundError(farm.name, category.name)
        
        # 3. VALIDAR SALDO SUFICIENTE
        validate_sufficient_stock(
            current_stock=stock_balance.current_quantity,
            requested_quantity=quantity,
            farm_name=stock_balance.farm.name,
            category_name=stock_balance.animal_category.name
        )
        
        # 4. CALCULAR NOVO SALDO
        new_quantity = stock_balance.current_quantity - quantity
        
        if new_quantity < 0:
            raise InsufficientStockError(
                farm_name=stock_balance.farm.name,
                category_name=stock_balance.animal_category.name,
                requested=quantity,
                available=stock_balance.current_quantity
            )
        
        # 5. OBTER RELACIONAMENTOS OPCIONAIS
        client = None
        if client_id:
            client = Client.objects.get(id=client_id)
        
        death_reason = None
        if death_reason_id:
            death_reason = DeathReason.objects.get(id=death_reason_id)
        
        # 6. CRIAR REGISTRO NO LEDGER (imutável)
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
        
        # 7. ATUALIZAR SALDO COM VERSIONING
        from django.db.models import F
        
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        
        # 8. VERIFICAR SUCESSO
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

        Comportamento:
        - ENTRADA → estorno diminui o saldo (desfaz o acréscimo)
        - SAÍDA   → estorno aumenta o saldo (devolve os animais)
        - Operações compostas (MANEJO, MUDANÇA_CATEGORIA, DESMAME) cancelam
          ambos os lados (IN e OUT) dentro da mesma transação atômica
        - O ledger permanece imutável: cria AnimalMovementCancellation como evento
        - Uma movimentação só pode ser cancelada uma vez (constraint OneToOne)

        Args:
            movement_id: UUID da movimentação a cancelar
            cancelled_by: Usuário que está realizando o cancelamento
            notes: Observação opcional sobre o motivo do cancelamento

        Returns:
            dict com informações do cancelamento para exibição na interface

        Raises:
            ValidationError: Se já cancelada
            InsufficientStockError: Se estorno de ENTRADA deixaria saldo negativo
            ConcurrencyError: Se houver conflito de versão
        """
        from inventory.models import AnimalMovementCancellation
        from django.db.models import F

        # 1. BUSCAR MOVIMENTO PRINCIPAL COM LOCK
        movement = (
            AnimalMovement.objects
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'related_movement__farm_stock_balance__farm',
                'related_movement__farm_stock_balance__animal_category',
            )
            .prefetch_related('cancellation')
            .select_for_update()
            .get(pk=movement_id)
        )

        # 2. VERIFICAR SE JÁ CANCELADO
        try:
            c = movement.cancellation
            raise ValidationError(
                f"Esta movimentação já foi cancelada em "
                f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                f"por {c.cancelled_by.username}."
            )
        except AnimalMovementCancellation.DoesNotExist:
            pass

        # 3. MONTAR LISTA DE MOVIMENTOS A CANCELAR
        #    Operações compostas têm related_movement (MANEJO, MUDANÇA_CATEGORIA, DESMAME)
        movements_to_cancel = [movement]

        if movement.related_movement_id:
            related = (
                AnimalMovement.objects
                .select_related(
                    'farm_stock_balance__farm',
                    'farm_stock_balance__animal_category',
                )
                .prefetch_related('cancellation')
                .select_for_update()
                .get(pk=movement.related_movement_id)
            )
            try:
                rc = related.cancellation
                raise ValidationError(
                    f"O movimento relacionado desta operação já foi cancelado em "
                    f"{rc.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                    f"por {rc.cancelled_by.username}."
                )
            except AnimalMovementCancellation.DoesNotExist:
                pass
            movements_to_cancel.append(related)

        # 4. PROCESSAR CADA MOVIMENTO
        cancellations_created = []

        for mov in movements_to_cancel:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                pk=mov.farm_stock_balance_id
            )

            balance_before = stock_balance.current_quantity

            if mov.movement_type == 'ENTRADA':
                # Estorno de ENTRADA → diminui saldo
                if balance_before < mov.quantity:
                    raise InsufficientStockError(
                        farm_name=stock_balance.farm.name,
                        category_name=stock_balance.animal_category.name,
                        requested=mov.quantity,
                        available=balance_before,
                    )
                new_quantity = balance_before - mov.quantity
            else:
                # Estorno de SAÍDA → devolve ao saldo
                new_quantity = balance_before + mov.quantity

            # Atualizar saldo com versioning otimista
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

            # Criar registro de cancelamento (imutável, append-only)
            cancellation = AnimalMovementCancellation.objects.create(
                movement=mov,
                cancelled_by=cancelled_by,
                quantity_restored=mov.quantity,
                balance_before=balance_before,
                balance_after=new_quantity,
                notes=notes,
            )
            cancellations_created.append(cancellation)

        # 5. RETORNAR DADOS PARA A INTERFACE
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
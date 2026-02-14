"""
Movement Service - Serviço de Movimentações.

Este é o CORAÇÃO do sistema de inventário.

Responsável por:
- Registrar entradas (NASCIMENTO, COMPRA, DESMAME, etc.)
- Registrar saídas (MORTE, VENDA, ABATE, DOAÇÃO)
- Garantir integridade de saldo (nunca negativo)
- Manter consistência entre ledger e snapshot
- Controle de concorrência

IMPORTANTE: TODA operação que altera saldo DEVE passar por este service.
"""
from django.db import transaction
from django.utils import timezone
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
        # Usar F() para garantir atomicidade e evitar race conditions
        from django.db.models import F
        
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version  # Validação de versão otimista
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        
        # 6. VERIFICAR SE ATUALIZAÇÃO FOI BEM-SUCEDIDA
        if updated_rows == 0:
            # Versão mudou entre o SELECT e o UPDATE
            raise ConcurrencyError("Saldo de estoque")
        
        # 7. RETORNAR MOVIMENTO CRIADO
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
        
        # Verificar se a operação é realmente de SAÍDA
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
        
        # 3. VALIDAR SALDO SUFICIENTE (INVARIANTE CRÍTICA)
        validate_sufficient_stock(
            current_stock=stock_balance.current_quantity,
            requested_quantity=quantity,
            farm_name=stock_balance.farm.name,
            category_name=stock_balance.animal_category.name
        )
        
        # 4. CALCULAR NOVO SALDO
        new_quantity = stock_balance.current_quantity - quantity
        
        # Garantia extra: nunca permitir saldo negativo
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
        
        # 7. ATUALIZAR SALDO CONSOLIDADO COM VERSIONING
        from django.db.models import F
        
        updated_rows = FarmStockBalance.objects.filter(
            id=stock_balance.id,
            version=stock_balance.version
        ).update(
            current_quantity=new_quantity,
            version=F('version') + 1,
            updated_at=timezone.now()
        )
        
        # 8. VERIFICAR SE ATUALIZAÇÃO FOI BEM-SUCEDIDA
        if updated_rows == 0:
            raise ConcurrencyError("Saldo de estoque")
        
        # 9. RETORNAR MOVIMENTO CRIADO
        return movement
    
    @staticmethod
    def get_operation_summary(movement: AnimalMovement) -> Dict[str, Any]:
        """
        Retorna um resumo legível da operação.
        
        Útil para exibição em interfaces e logs.
        """
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
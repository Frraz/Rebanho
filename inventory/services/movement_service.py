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

        ATENÇÃO — Por que NÃO usamos select_for_update() no fetch inicial:
        O PostgreSQL proíbe FOR UPDATE no lado nullable de um outer join.
        select_related() com FKs opcionais (related_movement, cancellation)
        gera LEFT OUTER JOINs, causando o erro:
          "FOR UPDATE cannot be applied to the nullable side of an outer join"

        Solução: separar em duas etapas:
          Etapa 1 — fetch sem lock (com select_related/prefetch_related) para
                    ler os dados e verificar se já está cancelado.
          Etapa 2 — lock pessimista APENAS no FarmStockBalance (query simples,
                    sem joins nullable), onde o lock é realmente necessário.

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

        # ── ETAPA 1: Fetch SEM lock ───────────────────────────────────────────
        # select_related e prefetch_related geram LEFT OUTER JOINs em relações
        # opcionais — incompatível com select_for_update() no PostgreSQL.
        # Por isso buscamos os dados aqui sem lock, apenas para leitura.
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

        # Verificar se o movimento principal já foi cancelado
        try:
            c = movement.cancellation
            raise ValidationError(
                f"Esta movimentação já foi cancelada em "
                f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
                f"por {c.cancelled_by.username}."
            )
        except AnimalMovementCancellation.DoesNotExist:
            pass

        # Para operações compostas (Manejo, Mudança de Categoria, Desmame),
        # buscar e verificar o lado relacionado também sem lock.
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

        # ── ETAPA 2: Lock + atualização de saldo ─────────────────────────────
        # select_for_update() aqui é seguro: FarmStockBalance não tem FKs
        # opcionais, portanto não gera LEFT OUTER JOINs.
        movements_to_cancel = [movement]
        if related_movement:
            movements_to_cancel.append(related_movement)

        cancellations_created = []

        for mov in movements_to_cancel:
            stock_balance = FarmStockBalance.objects.select_for_update().get(
                pk=mov.farm_stock_balance_id
            )

            balance_before = stock_balance.current_quantity

            if mov.movement_type == 'ENTRADA':
                # Estorno de ENTRADA → saldo diminui
                if balance_before < mov.quantity:
                    raise InsufficientStockError(
                        farm_name=stock_balance.farm.name,
                        category_name=stock_balance.animal_category.name,
                        requested=mov.quantity,
                        available=balance_before,
                    )
                new_quantity = balance_before - mov.quantity
            else:
                # Estorno de SAÍDA → saldo aumenta (animais voltam)
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

        REGRAS ESPECÍFICAS PARA MOVIMENTAÇÕES:
        - Operações simples (NASCIMENTO, COMPRA, SALDO): todos os campos editáveis
        - Operações compostas (MANEJO, DESMAME, MUDANCA_CATEGORIA):
            → quantidade BLOQUEADA (dois lados desalinhados seria inconsistência grave)
            → timestamp e metadata editáveis normalmente

        DESIGN: usa QuerySet.update() de forma deliberada para bypassar
        a proteção de ledger do model.save(). Este service é o único
        ponto autorizado a realizar essa operação.

        Args:
            movement_id: UUID da movimentação
            updated_by:  User que está editando
            data: dict com campos editáveis:
                quantity (int), timestamp (datetime), metadata (dict)

        Returns:
            dict com resultado para feedback na view

        Raises:
            ValidationError: movimento cancelado, saldo insuficiente,
                            tentativa de editar qty em operação composta
        """
        from django.db.models import F
        from inventory.models import AnimalMovementCancellation

        # ── 1. Buscar movement SEM lock (FKs nullable)
        try:
            movement = (
                AnimalMovement.objects
                .select_related('farm_stock_balance__farm', 'farm_stock_balance__animal_category')
                .get(id=movement_id)
            )
        except AnimalMovement.DoesNotExist:
            raise ValidationError("Movimentação não encontrada.")

        # ── 2. Bloquear edição de movimentos cancelados
        if AnimalMovementCancellation.objects.filter(movement_id=movement_id).exists():
            raise ValidationError("Movimentações canceladas não podem ser editadas.")

        # ── 3. Bloquear edição de quantidade em operações compostas
        COMPOSITE_TYPES = {
            OperationType.MANEJO_IN.value,
            OperationType.MANEJO_OUT.value,
            OperationType.MUDANCA_CATEGORIA_IN.value,
            OperationType.MUDANCA_CATEGORIA_OUT.value,
            OperationType.DESMAME_IN.value,
            OperationType.DESMAME_OUT.value,
        }

        new_quantity = data.get('quantity')
        is_composite = movement.operation_type in COMPOSITE_TYPES
        quantity_changed = new_quantity is not None and new_quantity != movement.quantity

        if quantity_changed and is_composite:
            raise ValidationError(
                "Não é possível editar a quantidade de operações compostas "
                "(Manejo, Desmame, Mudança de Categoria). "
                "Para corrigir, cancele a operação e registre novamente."
            )

        update_fields = {}
        balance_result = None

        # ── 4. Delta de quantidade (apenas operações simples)
        if quantity_changed:
            if new_quantity <= 0:
                raise ValidationError("Quantidade deve ser maior que zero.")

            balance = (
                FarmStockBalance.objects
                .select_related('farm', 'animal_category')
                .select_for_update(nowait=False)
                .get(id=movement.farm_stock_balance_id)
            )

            balance_before = balance.current_quantity

            if movement.movement_type == MovementType.ENTRADA.value:
                # Era ENTRADA: delta positivo → saldo aumenta mais; negativo → reduz
                delta = new_quantity - movement.quantity
                new_balance = balance.current_quantity + delta
                if new_balance < 0:
                    raise ValidationError(
                        f"Não é possível reduzir esta entrada: "
                        f"o saldo atual ({balance.current_quantity}) ficaria negativo."
                    )
            else:
                # Era SAÍDA: delta positivo → precisamos retirar mais do saldo
                delta = new_quantity - movement.quantity
                if delta > 0 and balance.current_quantity < delta:
                    raise ValidationError(
                        f"Saldo insuficiente para aumentar a saída. "
                        f"Disponível: {balance.current_quantity}, delta: {delta}."
                    )
                new_balance = balance.current_quantity - delta

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

        # ── 5. Campos sem impacto no saldo
        if 'timestamp' in data and data['timestamp']:
            update_fields['timestamp'] = data['timestamp']

        # ── 6. Merge de metadata + auditoria
        if 'metadata' in data or update_fields:
            current_meta = movement.metadata or {}
            if 'metadata' in data:
                current_meta.update({k: v for k, v in data['metadata'].items() if v is not None})
            current_meta['_edited_by'] = updated_by.username
            current_meta['_edited_at'] = timezone.now().isoformat()
            current_meta['_qty_before_edit'] = movement.quantity
            update_fields['metadata'] = current_meta

        # ── 7. Aplicar update — bypass INTENCIONAL do model.save()
        if update_fields:
            AnimalMovement.objects.filter(id=movement_id).update(**update_fields)

        from django.core.cache import cache
        farm_id = str(movement.farm_stock_balance.farm_id)
        cache.delete(f'farm_summary_{farm_id}')
        cache.delete(f'farm_history_{farm_id}')
        cache.delete('farms_list')

        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            f"[EDIÇÃO] Movimentação {movement_id} editada por {updated_by.username}. "
            f"Campos: {list(update_fields.keys())} | "
            f"Qty: {movement.quantity} → {update_fields.get('quantity', movement.quantity)}"
        )

        return {
            'farm': movement.farm_stock_balance.farm.name,
            'category': movement.farm_stock_balance.animal_category.name,
            'operation_display': movement.get_operation_type_display(),
            'is_composite': is_composite,
            'quantity_before': movement.quantity,
            'quantity_after': update_fields.get('quantity', movement.quantity),
            'balance': balance_result,
        }
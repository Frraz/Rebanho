"""
Transfer Service - Serviço de Transferências.

Responsável por operações COMPOSTAS que envolvem múltiplas movimentações:
- MANEJO: Transferência entre fazendas (saída + entrada)
- MUDANÇA DE CATEGORIA: Alteração de categoria (saída + entrada)

IMPORTANTE: Estas operações são ATÔMICAS - se uma parte falha, tudo é revertido.
"""
from django.db import transaction
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple

from inventory.models import AnimalMovement
from inventory.domain import (
    OperationType,
    validate_positive_quantity,
    validate_manejo_parameters,
    validate_category_change_parameters,
)
from inventory.services.movement_service import MovementService


class TransferService:
    """
    Serviço de Transferências (Operações Compostas).
    
    Garante que operações complexas sejam executadas atomicamente.
    """
    
    @staticmethod
    @transaction.atomic
    def execute_manejo(
        source_farm_id: str,
        target_farm_id: str,
        animal_category_id: str,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[AnimalMovement, AnimalMovement]:
        """
        Executa MANEJO: Transferência de animais entre fazendas.
        
        Esta é uma operação COMPOSTA que realiza:
        1. SAÍDA da fazenda origem (MANEJO_OUT)
        2. ENTRADA na fazenda destino (MANEJO_IN)
        
        A operação é ATÔMICA: se qualquer parte falhar, tudo é revertido.
        
        Args:
            source_farm_id: UUID da fazenda de origem
            target_farm_id: UUID da fazenda de destino
            animal_category_id: UUID da categoria dos animais
            quantity: Quantidade de animais a transferir
            user: Usuário que está registrando a operação
            timestamp: Data/hora da operação (default: agora)
            metadata: Dados adicionais em JSON (observações, etc.)
            ip_address: IP de origem da requisição
            
        Returns:
            Tuple[AnimalMovement, AnimalMovement]: 
                (movimento_saida, movimento_entrada)
                
        Raises:
            InvalidQuantityError: Se quantidade <= 0
            InsufficientStockError: Se saldo insuficiente na origem
            InvalidOperationError: Se origem == destino
        """
        
        # 1. VALIDAÇÕES DE DOMÍNIO
        validate_positive_quantity(quantity)
        validate_manejo_parameters(source_farm_id, target_farm_id)
        
        operation_timestamp = timestamp or timezone.now()
        operation_metadata = metadata or {}
        
        # Adicionar informação sobre a transferência no metadata
        saida_metadata = {
            **operation_metadata,
            'fazenda_destino': str(target_farm_id),
            'tipo_transferencia': 'manejo'
        }
        
        entrada_metadata = {
            **operation_metadata,
            'fazenda_origem': str(source_farm_id),
            'tipo_transferencia': 'manejo'
        }
        
        # 2. EXECUTAR SAÍDA DA FAZENDA ORIGEM
        movimento_saida = MovementService.execute_saida(
            farm_id=source_farm_id,
            animal_category_id=animal_category_id,
            operation_type=OperationType.MANEJO_OUT,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=saida_metadata,
            ip_address=ip_address,
        )
        
        # 3. EXECUTAR ENTRADA NA FAZENDA DESTINO
        try:
            movimento_entrada = MovementService.execute_entrada(
                farm_id=target_farm_id,
                animal_category_id=animal_category_id,
                operation_type=OperationType.MANEJO_IN,
                quantity=quantity,
                user=user,
                timestamp=operation_timestamp,
                metadata=entrada_metadata,
                ip_address=ip_address,
            )
        except Exception as e:
            # Se entrada falhar, a transação será revertida automaticamente
            # incluindo a saída que já foi feita
            raise e
        
        # 4. RETORNAR AMBOS OS MOVIMENTOS
        # Nota: A vinculação está no metadata, não precisamos de related_movement
        return (movimento_saida, movimento_entrada)
    
    @staticmethod
    @transaction.atomic
    def execute_mudanca_categoria(
        farm_id: str,
        source_category_id: str,
        target_category_id: str,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[AnimalMovement, AnimalMovement]:
        """
        Executa MUDANÇA DE CATEGORIA: Altera categoria de animais.
        
        Esta é uma operação COMPOSTA que realiza:
        1. SAÍDA da categoria origem (MUDANCA_CATEGORIA_OUT)
        2. ENTRADA na categoria destino (MUDANCA_CATEGORIA_IN)
        
        A operação é ATÔMICA: se qualquer parte falhar, tudo é revertido.
        
        Exemplo:
        - Fazenda tem 5 Bezerros e 1 Novilho
        - Executa mudança de 2 Bezerros → Novilho
        - Resultado: 3 Bezerros e 3 Novilhos
        
        Args:
            farm_id: UUID da fazenda
            source_category_id: UUID da categoria origem
            target_category_id: UUID da categoria destino
            quantity: Quantidade de animais a mudar de categoria
            user: Usuário que está registrando a operação
            timestamp: Data/hora da operação (default: agora)
            metadata: Dados adicionais em JSON (observações, etc.)
            ip_address: IP de origem da requisição
            
        Returns:
            Tuple[AnimalMovement, AnimalMovement]: 
                (movimento_saida, movimento_entrada)
                
        Raises:
            InvalidQuantityError: Se quantidade <= 0
            InsufficientStockError: Se saldo insuficiente na categoria origem
            InvalidOperationError: Se origem == destino
        """
        
        # 1. VALIDAÇÕES DE DOMÍNIO
        validate_positive_quantity(quantity)
        validate_category_change_parameters(source_category_id, target_category_id)
        
        operation_timestamp = timestamp or timezone.now()
        operation_metadata = metadata or {}
        
        # Adicionar informação sobre a mudança no metadata
        saida_metadata = {
            **operation_metadata,
            'categoria_destino': str(target_category_id),
            'tipo_transferencia': 'mudanca_categoria'
        }
        
        entrada_metadata = {
            **operation_metadata,
            'categoria_origem': str(source_category_id),
            'tipo_transferencia': 'mudanca_categoria'
        }
        
        # 2. EXECUTAR SAÍDA DA CATEGORIA ORIGEM
        movimento_saida = MovementService.execute_saida(
            farm_id=farm_id,
            animal_category_id=source_category_id,
            operation_type=OperationType.MUDANCA_CATEGORIA_OUT,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=saida_metadata,
            ip_address=ip_address,
        )
        
        # 3. EXECUTAR ENTRADA NA CATEGORIA DESTINO
        try:
            movimento_entrada = MovementService.execute_entrada(
                farm_id=farm_id,
                animal_category_id=target_category_id,
                operation_type=OperationType.MUDANCA_CATEGORIA_IN,
                quantity=quantity,
                user=user,
                timestamp=operation_timestamp,
                metadata=entrada_metadata,
                ip_address=ip_address,
            )
        except Exception as e:
            # Se entrada falhar, a transação será revertida automaticamente
            raise e
        
        # 4. RETORNAR AMBOS OS MOVIMENTOS
        return (movimento_saida, movimento_entrada)
    
    @staticmethod
    def get_transfer_summary(
        movimento_saida: AnimalMovement,
        movimento_entrada: AnimalMovement
    ) -> Dict[str, Any]:
        """
        Retorna um resumo legível da transferência.
        
        Útil para exibição em interfaces e logs.
        """
        is_manejo = movimento_saida.operation_type == OperationType.MANEJO_OUT.value
        
        if is_manejo:
            return {
                'tipo': 'Manejo',
                'origem': movimento_saida.farm_stock_balance.farm.name,
                'destino': movimento_entrada.farm_stock_balance.farm.name,
                'categoria': movimento_saida.farm_stock_balance.animal_category.name,
                'quantidade': movimento_saida.quantity,
                'data': movimento_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
                'usuario': movimento_saida.created_by.username,
            }
        else:
            return {
                'tipo': 'Mudança de Categoria',
                'fazenda': movimento_saida.farm_stock_balance.farm.name,
                'categoria_origem': movimento_saida.farm_stock_balance.animal_category.name,
                'categoria_destino': movimento_entrada.farm_stock_balance.animal_category.name,
                'quantidade': movimento_saida.quantity,
                'data': movimento_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
                'usuario': movimento_saida.created_by.username,
            }
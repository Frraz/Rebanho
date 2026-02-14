"""
Stock Query Service - Serviço de Consultas de Estoque.

Responsável por:
- Consultas otimizadas de saldo
- Listagens com filtros
- Agregações e estatísticas
- Recálculo de saldo a partir do histórico (auditoria)

IMPORTANTE: Este service é apenas para LEITURA.
Para alterações de saldo, use MovementService ou TransferService.
"""
from django.db.models import Sum, Q, F, Count
from django.utils import timezone
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from inventory.models import FarmStockBalance, AnimalMovement, AnimalCategory
from farms.models import Farm
from inventory.domain import MovementType


class StockQueryService:
    """
    Serviço de Consultas de Estoque (Read-Only).
    
    Todas as operações são otimizadas com select_related/prefetch_related.
    """
    
    @staticmethod
    def get_current_stock(farm_id: str, animal_category_id: str) -> Optional[FarmStockBalance]:
        """
        Obtém o saldo atual de uma combinação fazenda + categoria.
        
        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            
        Returns:
            FarmStockBalance ou None se não existir
        """
        try:
            return FarmStockBalance.objects.select_related(
                'farm', 'animal_category'
            ).get(
                farm_id=farm_id,
                animal_category_id=animal_category_id
            )
        except FarmStockBalance.DoesNotExist:
            return None
    
    @staticmethod
    def get_farm_stock_summary(farm_id: str) -> List[Dict[str, Any]]:
        """
        Retorna resumo de todos os saldos de uma fazenda.
        
        Args:
            farm_id: UUID da fazenda
            
        Returns:
            Lista de dicionários com categoria e quantidade
        """
        balances = FarmStockBalance.objects.filter(
            farm_id=farm_id
        ).select_related('animal_category').order_by('animal_category__name')
        
        return [
            {
                'categoria_id': str(balance.animal_category.id),
                'categoria_nome': balance.animal_category.name,
                'quantidade': balance.current_quantity,
                'ultima_atualizacao': balance.updated_at,
            }
            for balance in balances
        ]
    
    @staticmethod
    def get_all_farms_summary() -> List[Dict[str, Any]]:
        """
        Retorna resumo de saldos de todas as fazendas ativas.
        
        Returns:
            Lista de dicionários com fazenda e totais
        """
        farms = Farm.objects.filter(is_active=True).prefetch_related(
            'stock_balances__animal_category'
        )
        
        summary = []
        for farm in farms:
            total_animals = sum(
                balance.current_quantity 
                for balance in farm.stock_balances.all()
            )
            
            summary.append({
                'fazenda_id': str(farm.id),
                'fazenda_nome': farm.name,
                'total_animais': total_animals,
                'categorias': [
                    {
                        'categoria': balance.animal_category.name,
                        'quantidade': balance.current_quantity
                    }
                    for balance in farm.stock_balances.all()
                ]
            })
        
        return summary
    
    @staticmethod
    def get_categories_with_stock(farm_id: str) -> List[AnimalCategory]:
        """
        Retorna apenas categorias que possuem saldo > 0 em uma fazenda.
        
        Útil para dropdowns de seleção (só mostrar categorias disponíveis).
        
        Args:
            farm_id: UUID da fazenda
            
        Returns:
            Lista de AnimalCategory com saldo > 0
        """
        balances = FarmStockBalance.objects.filter(
            farm_id=farm_id,
            current_quantity__gt=0
        ).select_related('animal_category')
        
        return [balance.animal_category for balance in balances]
    
    @staticmethod
    def get_movement_history(
        farm_id: Optional[str] = None,
        animal_category_id: Optional[str] = None,
        operation_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[AnimalMovement]:
        """
        Retorna histórico de movimentações com filtros opcionais.
        
        Args:
            farm_id: Filtrar por fazenda (opcional)
            animal_category_id: Filtrar por categoria (opcional)
            operation_type: Filtrar por tipo de operação (opcional)
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)
            limit: Limite de registros (default: 100)
            
        Returns:
            Lista de AnimalMovement ordenada por timestamp DESC
        """
        queryset = AnimalMovement.objects.select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'created_by',
            'client',
            'death_reason'
        )
        
        # Aplicar filtros
        if farm_id:
            queryset = queryset.filter(farm_stock_balance__farm_id=farm_id)
        
        if animal_category_id:
            queryset = queryset.filter(
                farm_stock_balance__animal_category_id=animal_category_id
            )
        
        if operation_type:
            queryset = queryset.filter(operation_type=operation_type)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Ordenar e limitar
        return queryset.order_by('-timestamp')[:limit]
    
    @staticmethod
    def get_statistics(
        farm_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Retorna estatísticas de movimentações.
        
        Args:
            farm_id: Filtrar por fazenda (opcional)
            start_date: Data inicial (opcional)
            end_date: Data final (opcional)
            
        Returns:
            Dicionário com estatísticas agregadas
        """
        queryset = AnimalMovement.objects.all()
        
        # Aplicar filtros
        if farm_id:
            queryset = queryset.filter(farm_stock_balance__farm_id=farm_id)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        # Agregações
        stats = queryset.aggregate(
            total_entradas=Sum(
                'quantity',
                filter=Q(movement_type=MovementType.ENTRADA.value)
            ),
            total_saidas=Sum(
                'quantity',
                filter=Q(movement_type=MovementType.SAIDA.value)
            ),
            total_movimentacoes=Count('id'),
        )
        
        return {
            'total_entradas': stats['total_entradas'] or 0,
            'total_saidas': stats['total_saidas'] or 0,
            'saldo_liquido': (stats['total_entradas'] or 0) - (stats['total_saidas'] or 0),
            'total_movimentacoes': stats['total_movimentacoes'],
        }
    
    @staticmethod
    def recalculate_stock_from_ledger(
        farm_id: str,
        animal_category_id: str,
        up_to_date: Optional[datetime] = None
    ) -> int:
        """
        Recalcula o saldo a partir do histórico (ledger).
        
        IMPORTANTE: Esta função é para AUDITORIA e RECONCILIAÇÃO.
        O saldo oficial está em FarmStockBalance.
        
        Use para:
        - Verificar se há inconsistências
        - Gerar relatórios históricos
        - Debugging
        
        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            up_to_date: Calcular até esta data (opcional, default: agora)
            
        Returns:
            Saldo calculado a partir do ledger
        """
        movements = AnimalMovement.objects.filter(
            farm_stock_balance__farm_id=farm_id,
            farm_stock_balance__animal_category_id=animal_category_id
        )
        
        if up_to_date:
            movements = movements.filter(timestamp__lte=up_to_date)
        
        # Agregar entradas e saídas
        result = movements.aggregate(
            total_in=Sum(
                'quantity',
                filter=Q(movement_type=MovementType.ENTRADA.value)
            ),
            total_out=Sum(
                'quantity',
                filter=Q(movement_type=MovementType.SAIDA.value)
            )
        )
        
        total_in = result['total_in'] or 0
        total_out = result['total_out'] or 0
        
        calculated_balance = total_in - total_out
        
        return calculated_balance
    
    @staticmethod
    def verify_stock_consistency(farm_id: str, animal_category_id: str) -> Dict[str, Any]:
        """
        Verifica se o saldo consolidado está consistente com o ledger.
        
        Args:
            farm_id: UUID da fazenda
            animal_category_id: UUID da categoria
            
        Returns:
            Dicionário com resultado da verificação
        """
        # Saldo oficial (snapshot)
        stock_balance = StockQueryService.get_current_stock(farm_id, animal_category_id)
        
        if not stock_balance:
            return {
                'consistente': False,
                'erro': 'Saldo não encontrado'
            }
        
        # Saldo recalculado (ledger)
        calculated = StockQueryService.recalculate_stock_from_ledger(
            farm_id, animal_category_id
        )
        
        # Comparar
        is_consistent = (stock_balance.current_quantity == calculated)
        
        return {
            'consistente': is_consistent,
            'saldo_oficial': stock_balance.current_quantity,
            'saldo_calculado': calculated,
            'diferenca': stock_balance.current_quantity - calculated,
            'fazenda': stock_balance.farm.name,
            'categoria': stock_balance.animal_category.name,
        }
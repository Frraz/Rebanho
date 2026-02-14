"""
Inventory Services - Camada de aplicação.

Serviços disponíveis:
- MovementService: Registrar entradas e saídas
- StockQueryService: Consultas de saldo
"""

from .movement_service import MovementService
from .stock_query_service import StockQueryService

__all__ = [
    'MovementService',
    'StockQueryService',
]
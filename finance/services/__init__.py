"""
Finance Services — camada de aplicação.

Toda escrita no domínio financeiro passa por aqui. Views nunca gravam direto
nos modelos, pelo mesmo motivo que o inventário centraliza tudo no
MovementService: as invariantes (estoque, saldo, extrato) precisam de um único
lugar responsável por mantê-las.
"""

from .balance_service import BalanceService, BalanceType
from .payment_service import AdjustmentService, PaymentService
from .sale_service import SaleService

__all__ = [
    'SaleService',
    'PaymentService',
    'AdjustmentService',
    'BalanceService',
    'BalanceType',
]

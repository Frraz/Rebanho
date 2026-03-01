"""
Inventory Domain - Camada de domínio puro.

Este módulo expõe os conceitos fundamentais de negócio sem
dependências de framework ou infraestrutura.
"""

from .value_objects import MovementType, OperationType
from .exceptions import (
    DomainException,
    InsufficientStockError,
    StockBalanceNotFoundError,
    ConcurrencyError,
    InvalidQuantityError,
    InvalidOperationError,
    BusinessRuleViolation,
    WeaningCategoryNotFoundError,
)
from .validators import (
    validate_positive_quantity,
    validate_sufficient_stock,
    validate_operation_requirements,
    validate_manejo_parameters,
    validate_category_change_parameters,
    validate_weaning_parameters,
)

__all__ = [
    # Value Objects
    'MovementType',
    'OperationType',

    # Exceptions
    'DomainException',
    'InsufficientStockError',
    'StockBalanceNotFoundError',
    'ConcurrencyError',
    'InvalidQuantityError',
    'InvalidOperationError',
    'BusinessRuleViolation',
    'WeaningCategoryNotFoundError',

    # Validators
    'validate_positive_quantity',
    'validate_sufficient_stock',
    'validate_operation_requirements',
    'validate_manejo_parameters',
    'validate_category_change_parameters',
    'validate_weaning_parameters',
]
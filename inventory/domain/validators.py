"""
Domain Validators - Validações puras de regras de negócio.

Estas funções não dependem de Django ou qualquer framework.
Elas apenas validam regras de negócio e levantam exceções de domínio.
"""
from typing import Optional
from .exceptions import (
    InvalidQuantityError,
    InsufficientStockError,
    InvalidOperationError,
)
from .value_objects import OperationType


def validate_positive_quantity(quantity: int) -> None:
    """
    Valida que a quantidade é um número positivo.

    Args:
        quantity: Quantidade a validar

    Raises:
        InvalidQuantityError: Se quantidade for <= 0 ou não numérica
    """
    if not isinstance(quantity, int):
        raise InvalidQuantityError(quantity)

    if quantity <= 0:
        raise InvalidQuantityError(quantity)


def validate_sufficient_stock(
    current_stock: int,
    requested_quantity: int,
    farm_name: str,
    category_name: str
) -> None:
    """
    Valida que há estoque suficiente para uma operação de saída.

    Args:
        current_stock: Saldo atual disponível
        requested_quantity: Quantidade solicitada
        farm_name: Nome da fazenda (para mensagem de erro)
        category_name: Nome da categoria (para mensagem de erro)

    Raises:
        InsufficientStockError: Se requested_quantity > current_stock
    """
    if requested_quantity > current_stock:
        raise InsufficientStockError(
            farm_name=farm_name,
            category_name=category_name,
            requested=requested_quantity,
            available=current_stock
        )


def validate_operation_requirements(
    operation_type: OperationType,
    client_id: Optional[int] = None,
    death_reason_id: Optional[int] = None,
    related_movement_id: Optional[int] = None,
) -> None:
    """
    Valida que uma operação possui todos os dados obrigatórios.

    Args:
        operation_type: Tipo de operação sendo executada
        client_id: ID do cliente (se fornecido)
        death_reason_id: ID do motivo de morte (se fornecido)
        related_movement_id: ID do movimento relacionado (se fornecido)

    Raises:
        InvalidOperationError: Se dados obrigatórios estiverem ausentes
    """

    # Validar cliente obrigatório para VENDA e DOACAO
    if operation_type.requires_client() and not client_id:
        raise InvalidOperationError(
            operation=operation_type.value,
            reason="Esta operação requer cliente informado"
        )

    # Validar motivo de morte obrigatório para MORTE
    if operation_type.requires_death_reason() and not death_reason_id:
        raise InvalidOperationError(
            operation=operation_type.value,
            reason="Esta operação requer motivo de morte informado"
        )

    # Validar movimento relacionado para operações compostas
    if operation_type.requires_related_movement() and not related_movement_id:
        # Apenas warning, não erro crítico
        # O movimento relacionado é criado automaticamente em operações compostas
        pass


def validate_manejo_parameters(
    source_farm_id: Optional[int],
    target_farm_id: Optional[int],
) -> None:
    """
    Valida parâmetros específicos de operação de manejo.

    Args:
        source_farm_id: ID da fazenda origem
        target_farm_id: ID da fazenda destino

    Raises:
        InvalidOperationError: Se parâmetros estiverem inválidos
    """
    if not source_farm_id:
        raise InvalidOperationError(
            operation="MANEJO",
            reason="Fazenda de origem não informada"
        )

    if not target_farm_id:
        raise InvalidOperationError(
            operation="MANEJO",
            reason="Fazenda de destino não informada"
        )

    if source_farm_id == target_farm_id:
        raise InvalidOperationError(
            operation="MANEJO",
            reason="Fazenda de origem e destino não podem ser iguais"
        )


def validate_category_change_parameters(
    source_category_id: Optional[int],
    target_category_id: Optional[int],
) -> None:
    """
    Valida parâmetros específicos de mudança de categoria.

    Args:
        source_category_id: ID da categoria origem
        target_category_id: ID da categoria destino

    Raises:
        InvalidOperationError: Se parâmetros estiverem inválidos
    """
    if not source_category_id:
        raise InvalidOperationError(
            operation="MUDANCA_CATEGORIA",
            reason="Categoria de origem não informada"
        )

    if not target_category_id:
        raise InvalidOperationError(
            operation="MUDANCA_CATEGORIA",
            reason="Categoria de destino não informada"
        )

    if source_category_id == target_category_id:
        raise InvalidOperationError(
            operation="MUDANCA_CATEGORIA",
            reason="Categoria de origem e destino não podem ser iguais"
        )


def validate_weaning_parameters(
    farm_id: Optional[str],
    quantity_males: int,
    quantity_females: int,
) -> None:
    """
    Valida parâmetros específicos do processo de desmame.

    Regras:
    - Fazenda é obrigatória
    - Pelo menos uma das quantidades deve ser > 0
    - Quantidades não podem ser negativas

    Args:
        farm_id: UUID da fazenda
        quantity_males: Quantidade de bezerros machos a desmamar
        quantity_females: Quantidade de bezerros fêmeas a desmamar

    Raises:
        InvalidOperationError: Se parâmetros estiverem inválidos
    """
    if not farm_id:
        raise InvalidOperationError(
            operation="DESMAME",
            reason="Fazenda não informada"
        )

    if quantity_males < 0 or quantity_females < 0:
        raise InvalidOperationError(
            operation="DESMAME",
            reason="Quantidades não podem ser negativas"
        )

    if quantity_males == 0 and quantity_females == 0:
        raise InvalidOperationError(
            operation="DESMAME",
            reason=(
                "Informe a quantidade de pelo menos uma categoria "
                "(B. Macho ou B. Fêmea) para realizar o desmame"
            )
        )
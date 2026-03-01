"""
Domain Exceptions - Exceções específicas das regras de negócio.

Estas exceções representam violações de invariantes de domínio e não
devem ser confundidas com erros de infraestrutura ou validação de formulário.
"""


class DomainException(Exception):
    """Exceção base para todas as exceções de domínio"""

    def __init__(self, message: str, code: str = None):
        self.message = message
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


class InsufficientStockError(DomainException):
    """
    Violação da invariante: saldo nunca pode ser negativo.

    Levantada quando uma operação de saída tentaria deixar o saldo negativo.
    """

    def __init__(self, farm_name: str, category_name: str,
                 requested: int, available: int):
        message = (
            f"Estoque insuficiente na fazenda '{farm_name}' "
            f"para categoria '{category_name}'. "
            f"Solicitado: {requested}, Disponível: {available}"
        )
        super().__init__(message, code="INSUFFICIENT_STOCK")
        self.farm_name = farm_name
        self.category_name = category_name
        self.requested = requested
        self.available = available


class StockBalanceNotFoundError(DomainException):
    """
    Registro de saldo não encontrado.

    Pode indicar que a combinação fazenda+categoria ainda não foi inicializada
    ou que há inconsistência nos dados.
    """

    def __init__(self, farm_name: str, category_name: str):
        message = (
            f"Registro de saldo não encontrado para fazenda '{farm_name}' "
            f"e categoria '{category_name}'"
        )
        super().__init__(message, code="STOCK_BALANCE_NOT_FOUND")
        self.farm_name = farm_name
        self.category_name = category_name


class ConcurrencyError(DomainException):
    """
    Conflito de concorrência detectado.

    Levantada quando o controle de versão otimista detecta que outro
    processo alterou o registro durante a transação atual.
    """

    def __init__(self, entity: str = "Registro"):
        message = (
            f"{entity} foi alterado por outra operação. "
            "Por favor, tente novamente."
        )
        super().__init__(message, code="CONCURRENCY_CONFLICT")


class InvalidQuantityError(DomainException):
    """
    Quantidade inválida fornecida.

    Levantada quando a quantidade é zero, negativa ou não numérica.
    """

    def __init__(self, quantity):
        message = f"Quantidade inválida: {quantity}. Deve ser um número positivo."
        super().__init__(message, code="INVALID_QUANTITY")
        self.quantity = quantity


class InvalidOperationError(DomainException):
    """
    Operação inválida ou não permitida no contexto atual.

    Exemplo: tentar fazer MANEJO sem especificar fazenda destino.
    """

    def __init__(self, operation: str, reason: str):
        message = f"Operação '{operation}' inválida: {reason}"
        super().__init__(message, code="INVALID_OPERATION")
        self.operation = operation
        self.reason = reason


class BusinessRuleViolation(DomainException):
    """
    Violação genérica de regra de negócio.

    Usar quando uma regra específica não tem exceção própria.
    """

    def __init__(self, rule: str, details: str = ""):
        message = f"Violação de regra de negócio: {rule}"
        if details:
            message += f". {details}"
        super().__init__(message, code="BUSINESS_RULE_VIOLATION")
        self.rule = rule


class WeaningCategoryNotFoundError(DomainException):
    """
    Categoria necessária para o processo de desmame não encontrada.

    Levantada quando uma das categorias do sistema envolvidas no desmame
    (B. Macho, B. Fêmea, Bois - 2A., Nov. - 2A.) não existe no banco.

    Indica que o seed de categorias do sistema não foi executado.
    """

    def __init__(self, slug: str):
        message = (
            f"Categoria do sistema com slug '{slug}' não encontrada. "
            "Execute o comando 'python manage.py seed_system_categories' "
            "para criar as categorias do sistema."
        )
        super().__init__(message, code="WEANING_CATEGORY_NOT_FOUND")
        self.slug = slug
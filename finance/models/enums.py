"""
finance/models/enums.py

Vocabulário do domínio financeiro.

Usamos `models.TextChoices` (e não o padrão `str, Enum` de
`inventory/domain/value_objects.py`) porque estes valores existem apenas como
choices de campos de modelo — o `get_<campo>_display()` do Django já entrega o
label em pt-BR sem precisar de um dicionário paralelo de tradução.
"""
from django.db import models


class SaleStatus(models.TextChoices):
    """Situação de uma venda."""

    ATIVA = 'ATIVA', 'Ativa'
    CANCELADA = 'CANCELADA', 'Cancelada'


class SaleOrigin(models.TextChoices):
    """
    Como a venda entrou no sistema.

    BACKFILL marca as vendas reconstruídas pela migração de dados a partir do
    ledger antigo. Isolar essas linhas é o que permite desfazer a migração sem
    tocar nas vendas cadastradas pelo usuário depois.
    """

    APP = 'APP', 'Cadastrada no sistema'
    BACKFILL = 'BACKFILL', 'Importada do histórico'


class PaymentType(models.TextChoices):
    """Forma de pagamento recebida do cliente."""

    DINHEIRO = 'DINHEIRO', 'Dinheiro'
    PIX = 'PIX', 'Pix'
    TRANSFERENCIA = 'TRANSFERENCIA', 'Transferência'
    CHEQUE = 'CHEQUE', 'Cheque'
    DEPOSITO = 'DEPOSITO', 'Depósito'
    OUTROS = 'OUTROS', 'Outros'


class EntryType(models.TextChoices):
    """
    Natureza do lançamento no extrato do cliente.

    DEBITO  → o cliente passa a dever mais (venda, ajuste de cobrança).
    CREDITO → o cliente passa a dever menos (pagamento, ajuste a favor dele).
    """

    DEBITO = 'DEBITO', 'Débito'
    CREDITO = 'CREDITO', 'Crédito'


class EntrySource(models.TextChoices):
    """Origem do lançamento — de onde ele nasceu."""

    VENDA = 'VENDA', 'Venda'
    PAGAMENTO = 'PAGAMENTO', 'Pagamento'
    AJUSTE = 'AJUSTE', 'Ajuste manual'


class DeletedObjectType(models.TextChoices):
    """O que foi apagado, registrado no log de exclusões."""

    VENDA = 'VENDA', 'Venda'
    PAGAMENTO = 'PAGAMENTO', 'Pagamento'
    AJUSTE = 'AJUSTE', 'Ajuste manual'

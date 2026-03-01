"""
Domain Value Objects - Objetos de valor imutáveis do domínio de inventário.

Estes objetos representam conceitos de negócio fundamentais e não possuem
dependências de framework ou infraestrutura.

CHANGELOG v2:
- Adicionado DESMAME_OUT (saída da categoria origem durante desmame)
- Adicionado DESMAME_IN (entrada na categoria destino durante desmame)
- DESMAME original renomeado para DESMAME_IN (retrocompatível no banco)
  ATENÇÃO: Se já existirem registros com operation_type='DESMAME' no banco,
  será necessária uma data migration para renomear para 'DESMAME_IN'.
"""
from enum import Enum


class MovementType(str, Enum):
    """
    Tipo fundamental de movimentação no ledger.

    ENTRADA: Aumenta o saldo (nascimento, compra, manejo recebido)
    SAÍDA: Diminui o saldo (morte, venda, manejo enviado)
    """
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]


class OperationType(str, Enum):
    """
    Tipos específicos de operações que geram movimentações.

    Cada operação possui regras de negócio específicas e pode ter
    metadados diferentes no campo JSON.
    """

    # === ENTRADAS ===
    NASCIMENTO = "NASCIMENTO"
    COMPRA = "COMPRA"
    MANEJO_IN = "MANEJO_IN"                      # Recebimento de outra fazenda
    MUDANCA_CATEGORIA_IN = "MUDANCA_CATEGORIA_IN"  # Entrada na nova categoria
    DESMAME_IN = "DESMAME_IN"                      # Entrada na categoria pós-desmame
    SALDO = "SALDO"                                # Ajuste positivo de saldo

    # === SAÍDAS ===
    MORTE = "MORTE"
    VENDA = "VENDA"
    ABATE = "ABATE"
    DOACAO = "DOACAO"
    MANEJO_OUT = "MANEJO_OUT"                      # Envio para outra fazenda
    MUDANCA_CATEGORIA_OUT = "MUDANCA_CATEGORIA_OUT"  # Saída da categoria origem
    DESMAME_OUT = "DESMAME_OUT"                    # Saída da categoria pré-desmame

    @classmethod
    def choices(cls):
        return [(item.value, item.name) for item in cls]

    @classmethod
    def entrada_operations(cls):
        """Retorna apenas operações de entrada"""
        return [
            cls.NASCIMENTO,
            cls.COMPRA,
            cls.MANEJO_IN,
            cls.MUDANCA_CATEGORIA_IN,
            cls.DESMAME_IN,
            cls.SALDO,
        ]

    @classmethod
    def saida_operations(cls):
        """Retorna apenas operações de saída"""
        return [
            cls.MORTE,
            cls.VENDA,
            cls.ABATE,
            cls.DOACAO,
            cls.MANEJO_OUT,
            cls.MUDANCA_CATEGORIA_OUT,
            cls.DESMAME_OUT,
        ]

    def get_movement_type(self) -> MovementType:
        """
        Determina automaticamente o tipo de movimento baseado na operação.

        Raises:
            ValueError: Se a operação não for reconhecida
        """
        if self in self.entrada_operations():
            return MovementType.ENTRADA
        elif self in self.saida_operations():
            return MovementType.SAIDA
        else:
            raise ValueError(f"Operação {self.value} não reconhecida")

    def requires_client(self) -> bool:
        """Indica se a operação requer cliente"""
        return self in [self.VENDA, self.DOACAO]

    def requires_death_reason(self) -> bool:
        """Indica se a operação requer motivo de morte"""
        return self == self.MORTE

    def requires_related_movement(self) -> bool:
        """Indica se a operação requer movimento relacionado"""
        return self in [
            self.MANEJO_IN,
            self.MANEJO_OUT,
            self.MUDANCA_CATEGORIA_IN,
            self.MUDANCA_CATEGORIA_OUT,
            self.DESMAME_IN,
            self.DESMAME_OUT,
        ]

    def is_weaning(self) -> bool:
        """Indica se a operação faz parte do processo de desmame"""
        return self in [self.DESMAME_IN, self.DESMAME_OUT]

    @classmethod
    def weaning_operations(cls):
        """Retorna operações de desmame"""
        return [cls.DESMAME_OUT, cls.DESMAME_IN]
"""
core/utils/decimal_utils.py

Utilitários para normalizar valores decimais no formato pt-BR.

Problema:
    Campos <input type="text"> com máscara pt-BR enviam valores como:
        "1.250,80"  →  deve virar  Decimal("1250.80")
        "1.250"     →  deve virar  Decimal("1250")   (sem decimal)
        "1250,8"    →  deve virar  Decimal("1250.8")
        "1250.8"    →  pode vir de copiar/colar em formato inglês

    O Django DecimalField espera "1250.80" (ponto como separador decimal).
    Com USE_THOUSAND_SEPARATOR=True e type="number", o browser não aceita
    vírgula e o conflito quebra o campo.

Solução:
    - Usar type="text" no widget
    - Normalizar o valor neste módulo antes da validação do Django
"""

import re
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


def normalize_pt_br_decimal(value: str) -> Decimal:
    """
    Converte uma string decimal no formato pt-BR para Decimal.

    Regras de conversão:
        "1.250,80"  → Decimal("1250.80")
        "1.250"     → Decimal("1250")
        "1250,80"   → Decimal("1250.80")
        "1250.80"   → Decimal("1250.80")   ← formato inglês (copiar/colar)
        "0"         → Decimal("0")

    Raises:
        ValidationError: se o valor não puder ser convertido.
    """
    if not value:
        raise ValidationError("Este campo é obrigatório.")

    raw = str(value).strip()

    # Remove espaços e símbolo de moeda que possam ter vindo da máscara
    raw = raw.replace("R$", "").replace(" ", "").strip()

    # Caso pt-BR: tem vírgula → vírgula é o separador decimal
    if "," in raw:
        # Remove pontos de milhar, troca vírgula por ponto
        raw = raw.replace(".", "").replace(",", ".")

    # Caso sem vírgula:
    #   "1.250" → pode ser milhar (pt-BR) OU decimal inglês
    #   Heurística: se o ponto separa exatamente 3 dígitos no final → milhar
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[0].isdigit():
            # "1.250" → milhar pt-BR → "1250"
            raw = raw.replace(".", "")
        # else: "1250.8" → formato inglês → deixa como está

    # Valida que restou apenas dígitos e ponto
    if not re.match(r'^\d+(\.\d+)?$', raw):
        raise ValidationError(
            f'Valor inválido: "{value}". '
            f'Use o formato 1.250,80 ou 1250,80.'
        )

    try:
        return Decimal(raw)
    except InvalidOperation:
        raise ValidationError(
            f'Não foi possível converter "{value}" para um número decimal.'
        )
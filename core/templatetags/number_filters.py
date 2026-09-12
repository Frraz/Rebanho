from decimal import Decimal, InvalidOperation
from django import template
from django.utils.formats import number_format

register = template.Library()


@register.filter
def format_num(value, decimal_places=None):
    """
    Formata número no padrão pt-BR:
      - separador de milhar: .
      - separador decimal: ,

    Uso:
      {{ valor|format_num }}                 -> automático (mantém decimais se existirem)
      {{ valor|format_num:2 }}               -> força 2 casas decimais
    """
    if value is None or value == "":
        return ""

    # converte decimal_places
    if decimal_places in (None, ""):
        dp = None
    else:
        try:
            dp = int(decimal_places)
        except (TypeError, ValueError):
            dp = None

    # tenta converter para Decimal de forma robusta
    try:
        if isinstance(value, Decimal):
            dec = value
        else:
            s = str(value).strip()

            # aceita entrada pt-BR: "1.234,56"
            s = s.replace(".", "").replace(",", ".")
            dec = Decimal(s)
    except (InvalidOperation, ValueError):
        return str(value)

    # dp automático
    if dp is None:
        if dec == dec.to_integral():
            dp = 0
        else:
            dp = min(max(-dec.as_tuple().exponent, 1), 6)

    return number_format(dec, decimal_pos=dp, use_l10n=True, force_grouping=True)


@register.filter
def peso_fmt(value):
    """
    Formata peso ou valor no padrão pt-BR, sempre com 2 casas decimais.

    Exemplos:
      1550       -> "1.550,00"
      1550.5     -> "1.550,50"
      "15000.00" -> "15.000,00"
      "1.550,00" -> "1.550,00"
      ""         -> ""
      None       -> ""

    Uso: {{ movement.metadata.peso|peso_fmt }}

    ─────────────────────────────────────────────────────────────────────────
    CORREÇÃO — o ponto sem vírgula é DECIMAL, não milhar

    A versão anterior fazia `s.replace(".", "").replace(",", ".")` em qualquer
    string. O problema é que os pesos e preços gravados no `metadata` vêm de
    `str(Decimal)`, onde o ponto é o separador decimal. Resultado prático:

        "15000.00"  →  "1500000"  →  exibido como  R$ 1.500.000,00

    ou seja, todo valor com centavos aparecia cem vezes maior na listagem de
    ocorrências e nos PDFs de relatório.

    A regra correta, e a mesma usada em finance/utils/money.py:
      • tem vírgula  → é digitação pt-BR: o ponto é milhar
      • não tem      → o ponto é decimal
    """
    if value is None or value == "":
        return ""

    try:
        if isinstance(value, Decimal):
            dec = value
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, (int, float)):
            dec = Decimal(str(value))
        else:
            s = str(value).strip().replace("R$", "").replace(" ", "")
            if "," in s:
                # Digitação pt-BR: ponto é milhar, vírgula é decimal.
                s = s.replace(".", "").replace(",", ".")
            # Sem vírgula: o ponto já é o separador decimal — não remover.
            dec = Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return str(value)

    return number_format(dec, decimal_pos=2, use_l10n=True, force_grouping=True)


@register.filter
def year_fmt(value):
    """
    Exibe o ano sem separador de milhar.
    Necessário porque USE_THOUSAND_SEPARATOR=True formata 2026 como "2.026".

    Exemplos:
      2026  -> "2026"
      2026  -> "2026"  (mesmo que passado como int ou string)

    Uso: {{ ano|year_fmt }}
    """
    if value is None or value == "":
        return ""
    try:
        return str(int(value))
    except (ValueError, TypeError):
        return str(value)
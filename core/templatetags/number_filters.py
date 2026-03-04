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
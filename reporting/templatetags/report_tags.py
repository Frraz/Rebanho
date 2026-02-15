from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Obtém item de dicionário pelo key."""
    if dictionary is None:
        return 0
    val = dictionary.get(key, 0)
    return val if val else 0


@register.filter
def sum_values(value):
    """
    Soma valores de um dict ou dict_values.
    Aceita: dict, dict_values, list, ou qualquer iterável de números.
    """
    if not value:
        return 0
    try:
        # Se for dict, pega os valores
        if isinstance(value, dict):
            return sum(v for v in value.values() if v)
        # Se for dict_values, list, ou outro iterável
        return sum(v for v in value if v)
    except (TypeError, ValueError):
        return 0


@register.filter
def show_or_dash(value):
    """Retorna '-' se valor for 0 ou None."""
    if not value:
        return '-'
    return value
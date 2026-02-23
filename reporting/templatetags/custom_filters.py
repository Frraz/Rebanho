# core/templatetags/custom_filters.py (ou crie em qualquer app)
"""
Template tags customizados para formatação de datas em português brasileiro.
"""
from django import template
from datetime import datetime
import locale

register = template.Library()

# Mapeamento de meses em português
MESES_PT = {
    1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
    5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
    9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
}

DIAS_SEMANA_PT = {
    0: 'segunda-feira', 1: 'terça-feira', 2: 'quarta-feira',
    3: 'quinta-feira', 4: 'sexta-feira', 5: 'sábado', 6: 'domingo'
}


@register.filter(name='mes_pt')
def mes_pt(value):
    """
    Retorna o nome do mês em português.
    Uso: {{ data|mes_pt }}
    """
    if isinstance(value, datetime):
        mes_num = value.month
    elif isinstance(value, int):
        mes_num = value
    else:
        return value
    
    return MESES_PT.get(mes_num, value)


@register.filter(name='data_completa_pt')
def data_completa_pt(value):
    """
    Formata data completa em português.
    Exemplo: "segunda-feira, 23 de fevereiro de 2026"
    Uso: {{ data|data_completa_pt }}
    """
    if not isinstance(value, datetime):
        try:
            value = datetime.strptime(str(value), '%Y-%m-%d')
        except:
            return value
    
    dia_semana = DIAS_SEMANA_PT[value.weekday()]
    mes = MESES_PT[value.month]
    
    return f"{dia_semana}, {value.day} de {mes} de {value.year}"


@register.filter(name='data_curta_pt')
def data_curta_pt(value):
    """
    Formata data curta em português.
    Exemplo: "23 de fevereiro de 2026"
    Uso: {{ data|data_curta_pt }}
    """
    if not isinstance(value, datetime):
        try:
            value = datetime.strptime(str(value), '%Y-%m-%d')
        except:
            return value
    
    mes = MESES_PT[value.month]
    return f"{value.day} de {mes} de {value.year}"


@register.simple_tag
def saudacao():
    """
    Retorna saudação baseada na hora do dia.
    Uso: {% saudacao %}
    """
    hora = datetime.now().hour
    
    if hora < 12:
        return "Bom dia"
    elif hora < 18:
        return "Boa tarde"
    else:
        return "Boa noite"


@register.simple_tag
def emoji_saudacao():
    """
    Retorna emoji baseado na hora do dia.
    Uso: {% emoji_saudacao %}
    """
    hora = datetime.now().hour
    
    if hora < 12:
        return "🌅"
    elif hora < 18:
        return "☀️"
    else:
        return "🌙"
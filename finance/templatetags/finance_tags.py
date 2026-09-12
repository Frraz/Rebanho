"""
finance/templatetags/finance_tags.py

Filtros de exibição do módulo financeiro.

POR QUE NÃO USAR `peso_fmt` PARA DINHEIRO
    `core.templatetags.number_filters.peso_fmt` faz
    `s.replace(".", "").replace(",", ".")` em qualquer string, sem checar se o
    ponto é milhar ou decimal. Isso funciona para o que o usuário digitou, mas
    quebra para o que o sistema gravou: `"15000.00"` (formato de `str(Decimal)`)
    vira `"1500000"` e aparece na tela como **R$ 1.500.000,00**.

    Os valores do módulo financeiro vêm de `DecimalField`, então o filtro aqui
    trata `Decimal` diretamente e nunca cai naquele caminho de string.
"""
from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format
from django.utils.safestring import mark_safe

register = template.Library()

ZERO = Decimal('0.00')


def _to_decimal(value):
    """Converte para Decimal sem a heurística de milhar (ver docstring)."""
    if value is None or value == '':
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None
    try:
        from finance.utils.money import parse_stored_amount

        return parse_stored_amount(value)
    except Exception:
        return None


@register.filter
def moeda(value):
    """
    Formata um valor em reais no padrão pt-BR, sem o símbolo.

        Decimal('15000.5') → "15.000,50"
        None               → "—"
    """
    numero = _to_decimal(value)
    if numero is None:
        return '—'
    return number_format(numero, decimal_pos=2, use_l10n=True, force_grouping=True)


@register.filter
def moeda_rs(value):
    """Igual a `moeda`, com o prefixo R$."""
    numero = _to_decimal(value)
    if numero is None:
        return '—'
    return f"R$ {moeda(numero)}"


@register.filter
def saldo_classe(value):
    """
    Classe Tailwind conforme o sinal do saldo.

    Vermelho = o cliente deve. Verde = tem crédito. Cinza = quitado.
    """
    numero = _to_decimal(value)
    if numero is None or numero == ZERO:
        return 'text-gray-500'
    return 'text-red-600' if numero < ZERO else 'text-emerald-600'


@register.filter
def saldo_rotulo(value):
    """Texto curto explicando o saldo, para não depender só da cor."""
    numero = _to_decimal(value)
    if numero is None or numero == ZERO:
        return 'Quitado'
    return 'Devendo' if numero < ZERO else 'Crédito'


@register.filter
def saldo_formatado(value):
    """
    Saldo com sinal explícito e valor absoluto.

    Mostrar "−R$ 10.000,00" comunica melhor que "R$ -10000.00", e o sinal
    aparece antes do símbolo, como se escreve em português.
    """
    numero = _to_decimal(value)
    if numero is None:
        return '—'
    if numero == ZERO:
        return 'R$ 0,00'
    sinal = '−' if numero < ZERO else '+'
    return mark_safe(f"{sinal}&nbsp;R$ {moeda(abs(numero))}")


@register.filter
def peso_kg(value):
    """Peso em kg no padrão pt-BR."""
    numero = _to_decimal(value)
    if numero is None:
        return '—'
    return number_format(numero, decimal_pos=2, use_l10n=True, force_grouping=True)


@register.filter
def buscar_por_id(queryset, id_str):
    """
    Acha o objeto de um queryset/lista cujo `pk` bate com `id_str`.

    Usado para re-selecionar o cliente atual nos filtros de listagem: o
    filtro só guarda o id na URL, e o client_picker precisa do objeto para
    mostrar o nome já preenchido na caixa de busca.
    """
    if not id_str:
        return None
    for obj in queryset:
        if str(obj.pk) == str(id_str):
            return obj
    return None


@register.filter
def preco_kg(value):
    """
    Preço por quilo.

    Guardamos 4 casas para não perder precisão no rateio, mas exibir
    "10,0000" polui a leitura — mostramos 2 casas quando as duas últimas
    são zero.
    """
    numero = _to_decimal(value)
    if numero is None:
        return '—'
    casas = 2 if numero == numero.quantize(Decimal('0.01')) else 4
    return number_format(numero, decimal_pos=casas, use_l10n=True, force_grouping=True)

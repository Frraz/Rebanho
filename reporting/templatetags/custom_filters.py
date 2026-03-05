"""
Template tags customizados para formatação de datas em português brasileiro.

Objetivos desta versão:
- Não depender de locale do sistema operacional (evita bugs em produção).
- Aceitar date, datetime, strings comuns e inteiros (mês).
- Expor filtros úteis para relatórios:
  - mes_pt
  - ano_pt
  - mes_ano_pt
  - mes_ano_anterior_pt   (ex.: "dezembro/2025" ou "DEZEMBRO 2025")
  - data_completa_pt
  - data_curta_pt
- Tags:
  - saudacao
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Union

from django import template
from django.utils.dateparse import parse_date, parse_datetime

register = template.Library()

MESES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}

DIAS_SEMANA_PT = {
    0: "segunda-feira",
    1: "terça-feira",
    2: "quarta-feira",
    3: "quinta-feira",
    4: "sexta-feira",
    5: "sábado",
    6: "domingo",
}


def _to_date(value: Any) -> Optional[date]:
    """
    Converte value para date quando possível.
    Aceita: date, datetime, "YYYY-MM-DD", "YYYY-MM-DDTHH:MM[:SS[.uuuuuu]][Z]", etc.
    """
    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, (int, float)):
        # não faz sentido para data
        return None

    s = str(value).strip()
    if not s:
        return None

    # tenta datetime primeiro (cobre ISO com hora)
    dt = parse_datetime(s)
    if dt:
        return dt.date()

    d = parse_date(s)
    if d:
        return d

    # fallback: tenta formato simples mais comum
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def _month_year_previous(d: date) -> tuple[int, int]:
    """Retorna (month, year) do mês anterior ao date d."""
    if d.month == 1:
        return 12, d.year - 1
    return d.month - 1, d.year


@register.filter(name="mes_pt")
def mes_pt(value: Any) -> str:
    """
    Retorna o nome do mês em português.

    Uso:
      {{ data|mes_pt }}     (data/datetime/string)
      {{ 3|mes_pt }}        -> "março"
    """
    if value is None or value == "":
        return ""

    if isinstance(value, int):
        return MESES_PT.get(value, str(value))

    d = _to_date(value)
    if not d:
        return str(value)

    return MESES_PT.get(d.month, str(d.month))


@register.filter(name="ano_pt")
def ano_pt(value: Any) -> str:
    """Retorna o ano (YYYY) de uma data."""
    d = _to_date(value)
    if not d:
        return ""
    return str(d.year)


@register.filter(name="mes_ano_pt")
def mes_ano_pt(value: Any) -> str:
    """
    Retorna "mês/ano" em pt-BR: "março/2026".
    """
    d = _to_date(value)
    if not d:
        return ""
    return f"{MESES_PT.get(d.month, d.month)}/{d.year}"


@register.filter(name="mes_ano_anterior_pt")
def mes_ano_anterior_pt(value: Any, uppercase: bool = False) -> str:
    """
    Retorna "mês ano" do mês anterior à data informada.
    Ex.: se value é 2026-01-10 -> "dezembro 2025"

    Uso:
      {{ report.period.start|mes_ano_anterior_pt }}
    """
    d = _to_date(value)
    if not d:
        return ""

    m, y = _month_year_previous(d)
    texto = f"{MESES_PT.get(m, m)} {y}"
    return texto.upper() if uppercase else texto


@register.filter(name="data_completa_pt")
def data_completa_pt(value: Any) -> str:
    """
    Formata data completa em português.
    Exemplo: "segunda-feira, 23 de fevereiro de 2026"

    Uso: {{ data|data_completa_pt }}
    """
    d = _to_date(value)
    if not d:
        return str(value) if value is not None else ""

    # weekday(): Monday=0 ... Sunday=6
    dia_semana = DIAS_SEMANA_PT.get(d.weekday(), "")
    mes = MESES_PT.get(d.month, str(d.month))
    return f"{dia_semana}, {d.day} de {mes} de {d.year}"


@register.filter(name="data_curta_pt")
def data_curta_pt(value: Any) -> str:
    """
    Formata data curta em português.
    Exemplo: "23 de fevereiro de 2026"

    Uso: {{ data|data_curta_pt }}
    """
    d = _to_date(value)
    if not d:
        return str(value) if value is not None else ""

    mes = MESES_PT.get(d.month, str(d.month))
    return f"{d.day} de {mes} de {d.year}"


@register.simple_tag
def saudacao() -> str:
    """
    Retorna saudação baseada na hora do dia.
    Uso: {% saudacao %}
    """
    hora = datetime.now().hour
    if hora < 12:
        return "Bom dia"
    if hora < 18:
        return "Boa tarde"
    return "Boa noite"
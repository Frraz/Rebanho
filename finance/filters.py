"""
finance/filters.py

Leitura do filtro de período das telas financeiras (mês, ano, ou "todos").

POR QUE NÃO REUSAR `reporting.views._get_period_from_request`
    Este helper existe separado porque é usado por várias telas do app
    `finance` (Venda, Pagamento, Fluxo Financeiro, Exclusões), com um
    dicionário de retorno próprio (`inicio`/`fim`/`contiguo`) pensado para
    alimentar tanto o filtro do queryset quanto o rótulo do período nos PDFs.

Regras do filtro:
    • mês "Todos" e ano "Todos" → nada filtrado (ou o padrão, se
      `padrao_mes_atual=True` e nada foi enviado no GET)
    • só o ano                  → o ano inteiro
    • mês e ano                 → aquele mês específico
    • só o mês (ano "Todos")    → aquele mês em qualquer ano — não é um
      intervalo contínuo, então `inicio`/`fim` ficam `None` e `contiguo` vale
      `False` (quem usa `inicio`/`fim` para calcular algo em sequência, como o
      saldo acumulado do Fluxo Financeiro, deve checar essa flag antes)
"""
import calendar
from datetime import date

MESES = [
    ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
    ('4', 'Abril'), ('5', 'Maio'), ('6', 'Junho'),
    ('7', 'Julho'), ('8', 'Agosto'), ('9', 'Setembro'),
    ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
]

MESES_NOMES = {int(num): nome for num, nome in MESES}


def anos_disponiveis(hoje=None):
    """Anos oferecidos nos selects: cinco para trás e um para frente."""
    hoje = hoje or date.today()
    return list(range(hoje.year + 1, hoje.year - 6, -1))


def _inteiro(valor, minimo, maximo):
    """
    Converte texto de select para int dentro de uma faixa.

    Tolera o separador de milhar que o Django insere nos anos por causa do
    `USE_THOUSAND_SEPARATOR=True` ("2.026" chega assim em alguns navegadores).
    """
    if valor in (None, ''):
        return None
    try:
        limpo = str(valor).replace('.', '').replace(',', '').strip()
        numero = int(limpo)
    except (TypeError, ValueError):
        return None
    if numero < minimo or numero > maximo:
        return None
    return numero


def _primeiro_dia(ano, mes):
    return date(ano, mes, 1)


def _ultimo_dia(ano, mes):
    return date(ano, mes, calendar.monthrange(ano, mes)[1])


def parse_periodo(request, padrao_mes_atual=False, hoje=None):
    """
    Lê o mês/ano dos parâmetros GET.

    Args:
        request: o HttpRequest
        padrao_mes_atual: quando nada é informado, usa o mês corrente em vez
                          de não filtrar nada
        hoje: para testes

    Returns:
        dict com `inicio`, `fim` (date ou None, só quando o período é
        contínuo), `contiguo` e os valores crus para remontar os selects.
    """
    hoje = hoje or date.today()

    mes = _inteiro(request.GET.get('mes'), 1, 12)
    ano = _inteiro(request.GET.get('ano'), 1900, 2200)

    # Checar a PRESENÇA da chave, não o valor: um envio explícito do
    # formulário com "Todos" nos dois selects manda `mes=` e `ano=` vazios,
    # e isso precisa ser respeitado — não pode cair de volta no padrão.
    informou_algo = 'mes' in request.GET or 'ano' in request.GET

    if not informou_algo and padrao_mes_atual:
        mes, ano = hoje.month, hoje.year

    # Mês específico sem ano não forma um intervalo contínuo (seria "todos
    # os Dezembros", por exemplo, de anos diferentes).
    contiguo = not (mes and not ano)

    inicio = fim = None
    if contiguo:
        if mes and ano:
            inicio = _primeiro_dia(ano, mes)
            fim = _ultimo_dia(ano, mes)
        elif ano:
            inicio = date(ano, 1, 1)
            fim = date(ano, 12, 31)

    return {
        'inicio': inicio,
        'fim': fim,
        'mes': str(mes) if mes else '',
        'ano': str(ano) if ano else '',
        'tem_periodo': bool(mes or ano),
        'contiguo': contiguo,
    }


def rotulo_periodo(periodo):
    """Texto do período para o cabeçalho dos PDFs e da impressão."""
    inicio, fim = periodo.get('inicio'), periodo.get('fim')
    if inicio and fim:
        if inicio.month == 1 and fim.month == 12 and inicio.year == fim.year:
            return f"Ano de {inicio.year}"
        return f"{MESES_NOMES[inicio.month]} de {inicio.year}"
    if periodo.get('mes'):
        return f"{MESES_NOMES[int(periodo['mes'])]} (todos os anos)"
    return 'Todo o período'


def aplicar_periodo(queryset, periodo, campo='date'):
    """Aplica o filtro de mês/ano a um queryset."""
    if periodo.get('ano'):
        queryset = queryset.filter(**{f'{campo}__year': int(periodo['ano'])})
    if periodo.get('mes'):
        queryset = queryset.filter(**{f'{campo}__month': int(periodo['mes'])})
    return queryset


def contexto_periodo(periodo, hoje=None):
    """Dados que a tela precisa para redesenhar os selects de período."""
    return {
        'meses': MESES,
        'anos': anos_disponiveis(hoje),
        'mes_filtro': periodo['mes'],
        'ano_filtro': periodo['ano'],
        'periodo_label': rotulo_periodo(periodo),
    }

"""
finance/filters.py

Leitura dos filtros de tela (período, cliente, tipo de animal, etc.).

POR QUE NÃO REUSAR `reporting.views._get_period_from_request`
    Aquele helper resolve um único mês/ano (ou o ano inteiro com `month=0`), que
    é o que os relatórios de estoque precisam. As telas financeiras trabalham
    com INTERVALO — mês/ano de início e mês/ano de fim, podendo informar só o
    início. São perguntas diferentes, então são helpers diferentes.

Regras do intervalo:
    • nada informado        → conforme `padrao_mes_atual`
    • só o início           → do início do mês inicial até hoje
    • só o fim              → tudo até o fim do mês final
    • início e fim          → do primeiro dia do mês inicial ao último do final
    • fim anterior ao início → os dois são trocados, em vez de devolver vazio
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
    Lê o intervalo de datas dos parâmetros GET.

    Args:
        request: o HttpRequest
        padrao_mes_atual: quando nada é informado, usa o mês corrente
                          (comportamento do relatório de Fluxo Financeiro) em
                          vez de não filtrar nada (comportamento das listas)
        hoje: para testes

    Returns:
        dict com `inicio`, `fim` (date ou None) e os valores crus para
        remontar os selects na tela.
    """
    hoje = hoje or date.today()

    mes_inicio = _inteiro(request.GET.get('mes_inicio'), 1, 12)
    ano_inicio = _inteiro(request.GET.get('ano_inicio'), 1900, 2200)
    mes_fim = _inteiro(request.GET.get('mes_fim'), 1, 12)
    ano_fim = _inteiro(request.GET.get('ano_fim'), 1900, 2200)

    informou_algo = any(
        request.GET.get(chave) for chave in
        ('mes_inicio', 'ano_inicio', 'mes_fim', 'ano_fim')
    )

    if not informou_algo and padrao_mes_atual:
        mes_inicio, ano_inicio = hoje.month, hoje.year
        mes_fim, ano_fim = hoje.month, hoje.year

    # Mês sem ano assume o ano corrente; ano sem mês abrange o ano todo.
    ref_inicio = None
    if mes_inicio or ano_inicio:
        ref_inicio = (ano_inicio or hoje.year, mes_inicio or 1)

    ref_fim = None
    if mes_fim or ano_fim:
        ref_fim = (ano_fim or hoje.year, mes_fim or 12)

    # Fim antes do início: troca o PAR mês/ano e só depois calcula os limites.
    # Trocar as datas já calculadas daria um intervalo errado — o início
    # herdaria o último dia do mês e o fim, o primeiro.
    if ref_inicio and ref_fim and ref_inicio > ref_fim:
        ref_inicio, ref_fim = ref_fim, ref_inicio
        mes_inicio, ano_inicio, mes_fim, ano_fim = (
            mes_fim, ano_fim, mes_inicio, ano_inicio,
        )

    inicio = _primeiro_dia(ref_inicio[0], ref_inicio[1]) if ref_inicio else None

    if ref_fim:
        fim = _ultimo_dia(ref_fim[0], ref_fim[1])
    elif inicio is not None:
        # Só o início foi informado — vale até hoje.
        fim = hoje
    else:
        fim = None

    return {
        'inicio': inicio,
        'fim': fim,
        'mes_inicio': str(mes_inicio) if mes_inicio else '',
        'ano_inicio': str(ano_inicio) if ano_inicio else '',
        'mes_fim': str(mes_fim) if mes_fim else '',
        'ano_fim': str(ano_fim) if ano_fim else '',
        'tem_periodo': bool(inicio or fim),
    }


def rotulo_periodo(periodo):
    """Texto do período para o cabeçalho dos PDFs e da impressão."""
    inicio, fim = periodo.get('inicio'), periodo.get('fim')
    if not inicio and not fim:
        return 'Todo o período'
    if inicio and fim:
        if (inicio.year, inicio.month) == (fim.year, fim.month):
            return f"{MESES_NOMES[inicio.month]} de {inicio.year}"
        return (
            f"{MESES_NOMES[inicio.month]}/{inicio.year} "
            f"a {MESES_NOMES[fim.month]}/{fim.year}"
        )
    if inicio:
        return f"A partir de {MESES_NOMES[inicio.month]}/{inicio.year}"
    return f"Até {MESES_NOMES[fim.month]}/{fim.year}"


def aplicar_periodo(queryset, periodo, campo='date'):
    """Aplica o intervalo a um queryset."""
    if periodo.get('inicio'):
        queryset = queryset.filter(**{f'{campo}__gte': periodo['inicio']})
    if periodo.get('fim'):
        queryset = queryset.filter(**{f'{campo}__lte': periodo['fim']})
    return queryset


def contexto_periodo(periodo, hoje=None):
    """Dados que a tela precisa para redesenhar os selects de período."""
    return {
        'meses': MESES,
        'anos': anos_disponiveis(hoje),
        'mes_inicio': periodo['mes_inicio'],
        'ano_inicio': periodo['ano_inicio'],
        'mes_fim': periodo['mes_fim'],
        'ano_fim': periodo['ano_fim'],
        'periodo_label': rotulo_periodo(periodo),
    }

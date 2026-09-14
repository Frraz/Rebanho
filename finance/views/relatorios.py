"""
finance/views/relatorios.py

Os dois relatórios financeiros: Fluxo Financeiro e Saldos.

Aparecem no dropdown "Relatórios", junto de "Relatório por Fazenda",
"Fazendas Reunidas" e "Ficha de Controle Manual", e seguem o mesmo padrão
daquelas telas: filtros num card `print:hidden`, botão Imprimir com
`window.print()` e botão Exportar PDF apontando para uma rota irmã que
recebe os mesmos parâmetros.
"""
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from farms.models import Farm
from finance.filters import aplicar_periodo, contexto_periodo, parse_periodo, rotulo_periodo
from finance.models import EntrySource, EntryType, FinancialEntry
from finance.services import BalanceService
from finance.services.balance_service import BalanceType
from finance.views.pdf import render_pdf
from inventory.models import AnimalCategory
from operations.models import Client

logger = logging.getLogger(__name__)

ZERO = Decimal('0.00')
POR_PAGINA = 50


# ══════════════════════════════════════════════════════════════════════════════
# FLUXO FINANCEIRO
# ══════════════════════════════════════════════════════════════════════════════

def _ler_filtros_fluxo(request):
    return {
        # O cliente pediu que este relatório abra no mês e ano atuais.
        'periodo': parse_periodo(request, padrao_mes_atual=True),
        'cliente_id': request.GET.get('cliente', '').strip(),
        'categoria_id': request.GET.get('categoria', '').strip(),
        'fazenda_id': request.GET.get('fazenda', '').strip(),
        'natureza': request.GET.get('natureza', '').strip(),
        'origem': request.GET.get('origem', '').strip(),
    }


def _aplicar_filtros_fluxo(queryset, filtros):
    queryset = aplicar_periodo(queryset, filtros['periodo'], campo='date')

    if filtros['cliente_id']:
        queryset = queryset.filter(client_id=filtros['cliente_id'])

    if filtros['natureza'] in (EntryType.DEBITO, EntryType.CREDITO):
        queryset = queryset.filter(entry_type=filtros['natureza'])

    if filtros['origem'] in dict(EntrySource.choices):
        queryset = queryset.filter(source_type=filtros['origem'])

    if filtros['categoria_id']:
        # Só faz sentido para lançamentos de venda: o tipo de animal está nos
        # lotes. Pagamentos e ajustes não têm animal, então saem do resultado.
        queryset = queryset.filter(
            sale__items__animal_category_id=filtros['categoria_id']
        )

    if filtros['fazenda_id']:
        queryset = queryset.filter(sale__farm_id=filtros['fazenda_id'])

    return queryset.distinct()


def _consultar_fluxo(filtros):
    # Ordem cronológica crescente: a primeira linha da tabela é o lançamento
    # mais antigo do período, a última é o mais recente.
    queryset = (
        FinancialEntry.objects
        .select_related('client', 'sale', 'sale__farm', 'payment', 'created_by')
        .prefetch_related('sale__items__animal_category')
        .order_by('date', 'created_at')
    )
    return _aplicar_filtros_fluxo(queryset, filtros)


def _totais_fluxo(queryset):
    resultado = queryset.aggregate(
        debitos=Sum('amount', filter=Q(entry_type=EntryType.DEBITO)),
        creditos=Sum('amount', filter=Q(entry_type=EntryType.CREDITO)),
    )
    debitos = resultado['debitos'] or ZERO
    creditos = resultado['creditos'] or ZERO
    return {
        'debitos': debitos,
        'creditos': creditos,
        'resultado': creditos - debitos,
    }


def _com_saldo_acumulado(lancamentos, cliente_id, periodo):
    """
    Acrescenta a coluna de saldo acumulado.

    Só é calculada quando um único cliente está filtrado — somar o extrato de
    clientes diferentes numa coluna só não significaria nada — e quando o
    período filtrado é um intervalo contínuo: com um mês específico e ano
    "Todos", os lançamentos não formam uma sequência única, então não há um
    "saldo antes do período" que faça sentido.
    """
    if not cliente_id or not periodo.get('contiguo'):
        return lancamentos, None

    saldo = (
        BalanceService.get_running_balance_before(cliente_id, periodo['inicio'])
        if periodo.get('inicio') else ZERO
    )
    inicial = saldo

    # `lancamentos` já chega do mais antigo para o mais recente (ordem de
    # exibição da tela), que é a mesma ordem cronológica em que o saldo
    # precisa ser somado.
    for lancamento in lancamentos:
        saldo += lancamento.signed_amount
        lancamento.saldo_acumulado = saldo

    return lancamentos, inicial


def _mostra_acumulado(filtros):
    """Só mostra a coluna quando há um cliente e o período é contínuo."""
    return bool(filtros['cliente_id']) and filtros['periodo'].get('contiguo')


def _contexto_filtros_fluxo(filtros):
    contexto = {
        'cliente_filtro': filtros['cliente_id'],
        'categoria_filtro': filtros['categoria_id'],
        'fazenda_filtro': filtros['fazenda_id'],
        'natureza_filtro': filtros['natureza'],
        'origem_filtro': filtros['origem'],
        'clientes': Client.objects.filter(is_active=True).order_by('name'),
        'categorias': AnimalCategory.objects.filter(is_active=True).order_by(
            'display_order', 'name'
        ),
        'fazendas': Farm.objects.filter(is_active=True).order_by('name'),
        'naturezas': EntryType.choices,
        'origens': EntrySource.choices,
    }
    contexto.update(contexto_periodo(filtros['periodo']))
    return contexto


@login_required
@require_http_methods(["GET"])
def fluxo_financeiro_view(request):
    filtros = _ler_filtros_fluxo(request)
    queryset = _consultar_fluxo(filtros)
    totais = _totais_fluxo(queryset)

    paginator = Paginator(queryset, POR_PAGINA)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    lancamentos, saldo_inicial = _com_saldo_acumulado(
        list(page_obj.object_list), filtros['cliente_id'], filtros['periodo']
    )
    mostra_acumulado = _mostra_acumulado(filtros)

    params = request.GET.copy()
    params.pop('page', None)
    codificado = params.urlencode()

    contexto = {
        'page_obj': page_obj,
        'lancamentos': lancamentos,
        'total_count': paginator.count,
        'totais': totais,
        'saldo_inicial': saldo_inicial,
        # Saldo do cliente ao final do período inteiro — não só da página
        # atual, já que `totais['resultado']` soma o queryset filtrado
        # completo (sem paginação).
        'saldo_final': (
            saldo_inicial + totais['resultado'] if mostra_acumulado else None
        ),
        'mostra_acumulado': mostra_acumulado,
        'querystring': f'&{codificado}' if codificado else '',
        'cliente_selecionado': (
            Client.objects.filter(pk=filtros['cliente_id']).first()
            if filtros['cliente_id'] else None
        ),
    }
    contexto.update(_contexto_filtros_fluxo(filtros))
    return render(request, 'finance/relatorio_fluxo.html', contexto)


@login_required
@require_http_methods(["GET"])
def fluxo_financeiro_pdf_view(request):
    filtros = _ler_filtros_fluxo(request)
    queryset = _consultar_fluxo(filtros)
    totais = _totais_fluxo(queryset)

    lancamentos, saldo_inicial = _com_saldo_acumulado(
        list(queryset[:3000]), filtros['cliente_id'], filtros['periodo']
    )
    mostra_acumulado = _mostra_acumulado(filtros)

    return render_pdf(
        'finance/pdf/fluxo_pdf.html',
        {
            'lancamentos': lancamentos,
            'total_count': queryset.count(),
            'totais': totais,
            'saldo_inicial': saldo_inicial,
            'saldo_final': (
                saldo_inicial + totais['resultado'] if mostra_acumulado else None
            ),
            'mostra_acumulado': mostra_acumulado,
            'periodo_label': rotulo_periodo(filtros['periodo']),
            'resumo_filtros': _resumo_filtros_fluxo(filtros),
            'user': request.user,
        },
        nome_arquivo='fluxo-financeiro',
    )


def _resumo_filtros_fluxo(filtros):
    partes = []
    if filtros['cliente_id']:
        cliente = Client.objects.filter(pk=filtros['cliente_id']).first()
        if cliente:
            partes.append(f"Cliente: {cliente.name}")
    if filtros['categoria_id']:
        categoria = AnimalCategory.objects.filter(pk=filtros['categoria_id']).first()
        if categoria:
            partes.append(f"Tipo de animal: {categoria.name}")
    if filtros['fazenda_id']:
        fazenda = Farm.objects.filter(pk=filtros['fazenda_id']).first()
        if fazenda:
            partes.append(f"Fazenda: {fazenda.name}")
    if filtros['natureza']:
        partes.append(f"Natureza: {dict(EntryType.choices).get(filtros['natureza'])}")
    if filtros['origem']:
        partes.append(f"Origem: {dict(EntrySource.choices).get(filtros['origem'])}")
    return ' · '.join(partes)


# ══════════════════════════════════════════════════════════════════════════════
# SALDOS
# ══════════════════════════════════════════════════════════════════════════════

def _ler_filtros_saldos(request):
    return {
        'cliente_id': request.GET.get('cliente', '').strip(),
        'tipo_saldo': request.GET.get('tipo_saldo', '').strip(),
        'busca': request.GET.get('q', '').strip(),
        'incluir_inativos': request.GET.get('inativos', '').strip() == '1',
    }


def _consultar_saldos(filtros):
    clientes = Client.objects.all()
    if not filtros['incluir_inativos']:
        clientes = clientes.filter(is_active=True)

    if filtros['cliente_id']:
        clientes = clientes.filter(pk=filtros['cliente_id'])

    if filtros['busca']:
        clientes = clientes.filter(name__icontains=filtros['busca'])

    clientes = BalanceService.annotate_balance(clientes)

    if filtros['tipo_saldo']:
        clientes = BalanceService.filter_by_balance_type(clientes, filtros['tipo_saldo'])

    return clientes.order_by('saldo', 'name')


def _totais_saldos(clientes):
    """
    Totais da lista.

    Devedores e credores são somados separadamente: um total único esconderia
    que existem cinquenta mil a receber e dez mil de crédito, mostrando só a
    diferença.
    """
    total_devedor = ZERO
    total_credor = ZERO
    n_devedores = n_credores = n_quitados = 0

    for cliente in clientes:
        saldo = cliente.saldo or ZERO
        if saldo < ZERO:
            total_devedor += abs(saldo)
            n_devedores += 1
        elif saldo > ZERO:
            total_credor += saldo
            n_credores += 1
        else:
            n_quitados += 1

    return {
        'total_devedor': total_devedor,
        'total_credor': total_credor,
        'liquido': total_credor - total_devedor,
        'n_devedores': n_devedores,
        'n_credores': n_credores,
        'n_quitados': n_quitados,
    }


@login_required
@require_http_methods(["GET"])
def saldos_view(request):
    filtros = _ler_filtros_saldos(request)
    clientes = list(_consultar_saldos(filtros))

    return render(request, 'finance/relatorio_saldos.html', {
        'clientes': clientes,
        'total_count': len(clientes),
        'totais': _totais_saldos(clientes),
        'cliente_filtro': filtros['cliente_id'],
        'tipo_saldo_filtro': filtros['tipo_saldo'],
        'busca': filtros['busca'],
        'inativos_filtro': filtros['incluir_inativos'],
        'filtros_ativos': any([
            filtros['cliente_id'], filtros['tipo_saldo'],
            filtros['busca'], filtros['incluir_inativos'],
        ]),
        'todos_clientes': Client.objects.filter(is_active=True).order_by('name'),
        'tipos_saldo': BalanceType.CHOICES,
    })


@login_required
@require_http_methods(["GET"])
def saldos_pdf_view(request):
    filtros = _ler_filtros_saldos(request)
    clientes = list(_consultar_saldos(filtros))

    partes = []
    if filtros['tipo_saldo']:
        partes.append(
            f"Tipo de saldo: {dict(BalanceType.CHOICES).get(filtros['tipo_saldo'])}"
        )
    if filtros['cliente_id']:
        cliente = Client.objects.filter(pk=filtros['cliente_id']).first()
        if cliente:
            partes.append(f"Cliente: {cliente.name}")
    if filtros['busca']:
        partes.append(f"Busca: \"{filtros['busca']}\"")
    if filtros['incluir_inativos']:
        partes.append("Incluindo clientes inativos")

    return render_pdf(
        'finance/pdf/saldos_pdf.html',
        {
            'clientes': clientes,
            'total_count': len(clientes),
            'totais': _totais_saldos(clientes),
            'resumo_filtros': ' · '.join(partes),
            'user': request.user,
        },
        nome_arquivo='saldos-clientes',
    )

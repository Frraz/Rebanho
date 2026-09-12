"""
finance/views/exclusoes.py

Histórico de exclusões financeiras.

POR QUE ESTA TELA É NECESSÁRIA
    A tela de auditoria do sistema (`core/views_audit.py`) consulta a tabela
    viva de movimentações. Quando uma venda ou um pagamento é apagado, ele
    simplesmente deixa de existir lá — e some da auditoria junto.

    Esta é, portanto, a única tela onde um registro apagado continua visível.
    Sem ela, "apagar" viraria um buraco sem rastro no controle financeiro.
"""
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from finance.filters import aplicar_periodo, contexto_periodo, parse_periodo
from finance.models import DeletedObjectType, FinanceDeletionLog
from operations.models import Client

logger = logging.getLogger(__name__)

POR_PAGINA = 30


@login_required
@require_http_methods(["GET"])
def exclusoes_list_view(request):
    periodo = parse_periodo(request)

    busca = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    cliente_id = request.GET.get('cliente', '').strip()

    queryset = (
        FinanceDeletionLog.objects
        .select_related('client', 'deleted_by')
        .order_by('-deleted_at')
    )

    # O período filtra pela data do registro apagado (a data da venda ou do
    # pagamento), não pela data da exclusão — é assim que o usuário procura.
    queryset = aplicar_periodo(queryset, periodo, campo='object_date')

    if tipo in dict(DeletedObjectType.choices):
        queryset = queryset.filter(object_type=tipo)

    if cliente_id:
        queryset = queryset.filter(client_id=cliente_id)

    if busca:
        queryset = queryset.filter(
            Q(client__name__icontains=busca)
            | Q(reason__icontains=busca)
            | Q(deleted_by__username__icontains=busca)
        )

    paginator = Paginator(queryset, POR_PAGINA)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    params = request.GET.copy()
    params.pop('page', None)
    codificado = params.urlencode()

    contexto = {
        'page_obj': page_obj,
        'paginator': paginator,
        'total_count': paginator.count,
        'busca': busca,
        'tipo_filtro': tipo,
        'cliente_filtro': cliente_id,
        'tipos': DeletedObjectType.choices,
        'clientes': Client.objects.order_by('name'),
        'filtros_ativos': any([busca, tipo, cliente_id, periodo['tem_periodo']]),
        'querystring': f'&{codificado}' if codificado else '',
    }
    contexto.update(contexto_periodo(periodo))
    return render(request, 'finance/exclusoes_list.html', contexto)

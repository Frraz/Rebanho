"""
Operations Ocorrências Views - Morte, Abate, Venda, Doação.

CORREÇÕES CRÍTICAS:
  - AnimalOccurrence → AnimalMovement (modelo correto)
  - Filtro de fazenda via farm_stock_balance__farm_id
  - page_obj na context (não 'occurrences')
  - URL corrigida: ocorrencias:list
  - Adicionado filtro de período (mês/ano)
  - @login_required em todas as views
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone

from operations.forms import MorteForm, AbateForm, VendaForm, DoacaoForm
from inventory.services import MovementService
from inventory.domain import OperationType
from inventory.models import AnimalMovement

# Tipos de operação classificados como "ocorrências" (sempre saídas)
OCCURRENCE_TYPES = [
    OperationType.MORTE.value,
    OperationType.ABATE.value,
    OperationType.VENDA.value,
    OperationType.DOACAO.value,
]

OCCURRENCE_LABELS = [
    ('MORTE',  '☠️ Morte'),
    ('ABATE',  '🔪 Abate'),
    ('VENDA',  '💰 Venda'),
    ('DOACAO', '🎁 Doação'),
]


@login_required
def occurrence_list_view(request):
    """
    Lista de ocorrências com filtros, busca e paginação.

    Parâmetros GET:
        q      — busca livre (fazenda, animal, cliente, motivo)
        tipo   — MORTE | ABATE | VENDA | DOACAO
        farm   — UUID da fazenda
        mes    — número do mês (1-12)
        ano    — ano (ex: 2025)
        page   — página atual
    """
    from farms.models import Farm

    search   = request.GET.get('q', '').strip()
    tipo     = request.GET.get('tipo', '').strip()
    farm_id  = request.GET.get('farm', '').strip()
    mes_str  = request.GET.get('mes', '').strip()
    ano_str  = request.GET.get('ano', '').strip()

    # QuerySet base — apenas ocorrências, ordenadas por data
    qs = (
        AnimalMovement.objects
        .filter(operation_type__in=OCCURRENCE_TYPES)
        .select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'client',
            'death_reason',
            'created_by',
        )
        .order_by('-timestamp')
    )

    # Aplicar filtros
    if tipo and tipo in dict(OCCURRENCE_LABELS):
        qs = qs.filter(operation_type=tipo)

    if farm_id:
        qs = qs.filter(farm_stock_balance__farm_id=farm_id)

    if mes_str.isdigit():
        qs = qs.filter(timestamp__month=int(mes_str))

    if ano_str.isdigit():
        qs = qs.filter(timestamp__year=int(ano_str))

    if search:
        qs = qs.filter(
            Q(farm_stock_balance__farm__name__icontains=search)
            | Q(farm_stock_balance__animal_category__name__icontains=search)
            | Q(client__name__icontains=search)
            | Q(death_reason__name__icontains=search)
            | Q(metadata__observacao__icontains=search)
        )

    # Paginação
    paginator = Paginator(qs, 20)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    # Helpers para os selects de período
    ano_atual = timezone.now().year
    anos  = list(range(ano_atual, ano_atual - 6, -1))
    meses = [
        ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
        ('4', 'Abril'),   ('5', 'Maio'),      ('6', 'Junho'),
        ('7', 'Julho'),   ('8', 'Agosto'),    ('9', 'Setembro'),
        ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
    ]

    context = {
        # paginação
        'page_obj':       page_obj,
        'paginator':      paginator,
        'total_count':    paginator.count,
        # filtros ativos
        'search_term':    search,
        'tipo_filtro':    tipo,
        'farm_filtro':    farm_id,
        'mes_filtro':     mes_str,
        'ano_filtro':     ano_str,
        'filtros_ativos': any([search, tipo, farm_id, mes_str, ano_str]),
        # selects
        'farms':  Farm.objects.filter(is_active=True).order_by('name'),
        'tipos':  OCCURRENCE_LABELS,
        'anos':   anos,
        'meses':  meses,
    }
    return render(request, 'operations/occurrence_list.html', context)


# ── MORTE ─────────────────────────────────────────────────────────────────────

@login_required
def morte_create_view(request):
    if request.method == 'POST':
        form = MorteForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.MORTE,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    death_reason_id=str(form.cleaned_data['death_reason'].id),
                    metadata={
                        'observacao': form.cleaned_data.get('observacao', ''),
                        'peso': str(form.cleaned_data['peso']) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'☠️ Morte registrada: {movement.quantity} '
                    f'{movement.farm_stock_balance.animal_category.name}(s) '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar morte: {e}')
    else:
        form = MorteForm()

    return render(request, 'operations/occurrence_form.html', {
        'form': form, 'title': 'Registrar Morte', 'operation_type': 'morte',
    })


# ── ABATE ─────────────────────────────────────────────────────────────────────

@login_required
def abate_create_view(request):
    if request.method == 'POST':
        form = AbateForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.ABATE,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={
                        'observacao': form.cleaned_data.get('observacao', ''),
                        'peso': str(form.cleaned_data['peso']) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'🔪 Abate registrado: {movement.quantity} '
                    f'{movement.farm_stock_balance.animal_category.name}(s) '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar abate: {e}')
    else:
        form = AbateForm()

    return render(request, 'operations/occurrence_form.html', {
        'form': form, 'title': 'Registrar Abate', 'operation_type': 'abate',
    })


# ── VENDA ─────────────────────────────────────────────────────────────────────

@login_required
def venda_create_view(request):
    if request.method == 'POST':
        form = VendaForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.VENDA,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    client_id=str(form.cleaned_data['client'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={
                        'observacao':  form.cleaned_data.get('observacao', ''),
                        'peso':        str(form.cleaned_data['peso']) if form.cleaned_data.get('peso') else None,
                        'preco_total': str(form.cleaned_data['preco_total']) if form.cleaned_data.get('preco_total') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'💰 Venda registrada: {movement.quantity} '
                    f'{movement.farm_stock_balance.animal_category.name}(s) '
                    f'para {movement.client.name}.'
                )
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar venda: {e}')
    else:
        form = VendaForm()

    return render(request, 'operations/occurrence_form.html', {
        'form': form, 'title': 'Registrar Venda', 'operation_type': 'venda',
    })


# ── DOAÇÃO ────────────────────────────────────────────────────────────────────

@login_required
def doacao_create_view(request):
    if request.method == 'POST':
        form = DoacaoForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.DOACAO,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    client_id=str(form.cleaned_data['client'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={
                        'observacao': form.cleaned_data.get('observacao', ''),
                        'peso': str(form.cleaned_data['peso']) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'🎁 Doação registrada: {movement.quantity} '
                    f'{movement.farm_stock_balance.animal_category.name}(s) '
                    f'para {movement.client.name}.'
                )
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar doação: {e}')
    else:
        form = DoacaoForm()

    return render(request, 'operations/occurrence_form.html', {
        'form': form, 'title': 'Registrar Doação', 'operation_type': 'doacao',
    })
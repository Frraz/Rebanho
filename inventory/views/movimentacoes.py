"""
Inventory Movimentações Views.

CORREÇÃO em movement_list_view:
  - Substituído StockQueryService.get_movement_history() (retorna lista, sem paginação)
    por AnimalMovement.objects.filter(...) — QuerySet paginável
  - Adicionados filtros: fazenda, tipo de operação, período, busca livre
  - @login_required adicionado em todas as views (inclusive movement_list_view)
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.utils import timezone

from inventory.forms import (
    NascimentoForm, DesmameForm, SaldoForm, CompraForm,
    ManejoForm, MudancaCategoriaForm,
)
from inventory.services import MovementService
from inventory.domain import OperationType
from inventory.models import AnimalMovement
from operations.services import TransferService

# Tipos que NÃO são ocorrências (MORTE/ABATE/VENDA/DOACAO)
OCCURRENCE_TYPES = {
    OperationType.MORTE.value,
    OperationType.ABATE.value,
    OperationType.VENDA.value,
    OperationType.DOACAO.value,
}


@login_required
def movement_list_view(request):
    """
    Histórico de movimentações (entradas + transferências) com filtros e paginação.

    Parâmetros GET:
        q        — busca livre (fazenda, animal, usuário)
        farm     — UUID da fazenda
        tipo     — tipo de operação (ex: NASCIMENTO, COMPRA, MANEJO_SAIDA ...)
        mes      — número do mês (1-12)
        ano      — ano (ex: 2025)
        page     — página atual
    """
    from farms.models import Farm

    search  = request.GET.get('q', '').strip()
    farm_id = request.GET.get('farm', '').strip()
    tipo    = request.GET.get('tipo', '').strip()
    mes_str = request.GET.get('mes', '').strip()
    ano_str = request.GET.get('ano', '').strip()

    # Base: excluir ocorrências (elas têm sua própria listagem)
    qs = (
        AnimalMovement.objects
        .exclude(operation_type__in=OCCURRENCE_TYPES)
        .select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'created_by',
        )
        .order_by('-timestamp')
    )

    # Aplicar filtros
    if farm_id:
        qs = qs.filter(farm_stock_balance__farm_id=farm_id)

    if tipo:
        qs = qs.filter(operation_type=tipo)

    if mes_str.isdigit():
        qs = qs.filter(timestamp__month=int(mes_str))

    if ano_str.isdigit():
        qs = qs.filter(timestamp__year=int(ano_str))

    if search:
        qs = qs.filter(
            Q(farm_stock_balance__farm__name__icontains=search)
            | Q(farm_stock_balance__animal_category__name__icontains=search)
            | Q(created_by__username__icontains=search)
            | Q(metadata__observacao__icontains=search)
        )

    # Paginação
    paginator = Paginator(qs, 25)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    # Tipos disponíveis para o select (apenas os que existem no banco)
    tipos_disponiveis = (
        AnimalMovement.objects
        .exclude(operation_type__in=OCCURRENCE_TYPES)
        .values_list('operation_type', flat=True)
        .distinct()
        .order_by('operation_type')
    )

    # Helpers período
    ano_atual = timezone.now().year
    anos  = list(range(ano_atual, ano_atual - 6, -1))
    meses = [
        ('1', 'Jan'), ('2', 'Fev'), ('3', 'Mar'),
        ('4', 'Abr'), ('5', 'Mai'), ('6', 'Jun'),
        ('7', 'Jul'), ('8', 'Ago'), ('9', 'Set'),
        ('10', 'Out'), ('11', 'Nov'), ('12', 'Dez'),
    ]

    context = {
        'page_obj':         page_obj,
        'paginator':        paginator,
        'total_count':      paginator.count,
        'search_term':      search,
        'farm_filtro':      farm_id,
        'tipo_filtro':      tipo,
        'mes_filtro':       mes_str,
        'ano_filtro':       ano_str,
        'filtros_ativos':   any([search, farm_id, tipo, mes_str, ano_str]),
        'farms':            Farm.objects.filter(is_active=True).order_by('name'),
        'tipos_disponiveis': tipos_disponiveis,
        'anos':             anos,
        'meses':            meses,
    }
    return render(request, 'inventory/movement_list.html', context)


# ── NASCIMENTO ────────────────────────────────────────────────────────────────

@login_required
def nascimento_create_view(request):
    if request.method == 'POST':
        form = NascimentoForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.NASCIMENTO,
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
                    f'🐣 Nascimento registrado: {movement.quantity} '
                    f'{movement.farm_stock_balance.animal_category.name}(s) '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar nascimento: {e}')
    else:
        form = NascimentoForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Registrar Nascimento', 'operation_type': 'nascimento',
    })


# ── DESMAME ───────────────────────────────────────────────────────────────────

@login_required
def desmame_create_view(request):
    if request.method == 'POST':
        form = DesmameForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.DESMAME,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, f'🍼 Desmame registrado com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar desmame: {e}')
    else:
        form = DesmameForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Registrar Desmame',
    })


# ── SALDO ─────────────────────────────────────────────────────────────────────

@login_required
def saldo_create_view(request):
    if request.method == 'POST':
        form = SaldoForm(request.POST)
        if form.is_valid():
            try:
                MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.SALDO,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, '⚖️ Saldo ajustado com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro ao ajustar saldo: {e}')
    else:
        form = SaldoForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Ajustar Saldo',
    })


# ── COMPRA ────────────────────────────────────────────────────────────────────

@login_required
def compra_create_view(request):
    if request.method == 'POST':
        form = CompraForm(request.POST)
        if form.is_valid():
            try:
                MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.COMPRA,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={
                        'observacao':     form.cleaned_data.get('observacao', ''),
                        'peso':           str(form.cleaned_data['peso']) if form.cleaned_data.get('peso') else None,
                        'preco_unitario': str(form.cleaned_data['preco_unitario']) if form.cleaned_data.get('preco_unitario') else None,
                        'fornecedor':     form.cleaned_data.get('fornecedor', ''),
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, '🛒 Compra registrada com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar compra: {e}')
    else:
        form = CompraForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Registrar Compra',
    })


# ── MANEJO ────────────────────────────────────────────────────────────────────

@login_required
def manejo_create_view(request):
    if request.method == 'POST':
        form = ManejoForm(request.POST)
        if form.is_valid():
            try:
                saida, entrada = TransferService.execute_manejo(
                    source_farm_id=str(form.cleaned_data['farm'].id),
                    target_farm_id=str(form.cleaned_data['target_farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'🚚 Manejo executado: {saida.quantity} '
                    f'{saida.farm_stock_balance.animal_category.name}(s) '
                    f'de {saida.farm_stock_balance.farm.name} '
                    f'→ {entrada.farm_stock_balance.farm.name}.'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro no manejo: {e}')
    else:
        form = ManejoForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Registrar Manejo',
    })


# ── MUDANÇA DE CATEGORIA ──────────────────────────────────────────────────────

@login_required
def mudanca_categoria_create_view(request):
    if request.method == 'POST':
        form = MudancaCategoriaForm(request.POST)
        if form.is_valid():
            try:
                saida, entrada = TransferService.execute_mudanca_categoria(
                    farm_id=str(form.cleaned_data['farm'].id),
                    source_category_id=str(form.cleaned_data['animal_category'].id),
                    target_category_id=str(form.cleaned_data['target_category'].id),
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'🔄 Mudança realizada: {saida.quantity} '
                    f'{saida.farm_stock_balance.animal_category.name}(s) '
                    f'→ {entrada.farm_stock_balance.animal_category.name}(s) '
                    f'em {saida.farm_stock_balance.farm.name}.'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro na mudança de categoria: {e}')
    else:
        form = MudancaCategoriaForm()

    return render(request, 'inventory/movement_form.html', {
        'form': form, 'title': 'Mudança de Categoria',
    })
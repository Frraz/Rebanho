"""
Operations Ocorrências Views - Morte, Abate, Venda, Doação.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required  # ADICIONAR

from operations.forms import MorteForm, AbateForm, VendaForm, DoacaoForm
from inventory.services import MovementService, StockQueryService
from inventory.domain import OperationType
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q

@login_required
def occurrence_list_view(request):
    """Lista de ocorrências com filtros, busca e paginação."""
    tipo = request.GET.get('tipo', '')
    farm_id = request.GET.get('farm', '')
    search = request.GET.get('q', '').strip()

    qs = AnimalOccurrence.objects.select_related(
        'farm', 'animal_category', 'client', 'death_reason', 'created_by'
    ).order_by('-created_at')

    # Filtros
    if tipo:
        qs = qs.filter(occurrence_type=tipo)
    if farm_id:
        qs = qs.filter(farm_id=farm_id)

    # Busca
    if search:
        qs = qs.filter(
            Q(farm__name__icontains=search) |
            Q(animal_category__name__icontains=search) |
            Q(client__name__icontains=search) |
            Q(notes__icontains=search)
        )

    # Paginação
    paginator = Paginator(qs, 20)
    page = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page)
    except (EmptyPage, PageNotAnInteger):
        page_obj = paginator.page(1)

    from farms.models import Farm
    context = {
        'page_obj': page_obj,
        'paginator': paginator,
        'total_count': paginator.count,
        'search_term': search,
        'tipo_filtro': tipo,
        'farm_filtro': farm_id,
        'farms': Farm.objects.filter(is_active=True).order_by('name'),
        'tipos': [
            ('MORTE', '☠️ Morte'),
            ('ABATE', '🔪 Abate'),
            ('VENDA', '💰 Venda'),
            ('DOACAO', '🎁 Doação'),
        ],
    }
    return render(request, 'operations/occurrence_list.html', context)


@login_required
def morte_create_view(request):
    """Registra morte"""
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
                        'peso': str(form.cleaned_data.get('peso', '')) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'Morte registrada: {movement.quantity} {movement.farm_stock_balance.animal_category.name}(s) '
                    f'na {movement.farm_stock_balance.farm.name}'
                )
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar morte: {e}')
    else:
        form = MorteForm()
    
    context = {
        'form': form,
        'title': 'Registrar Morte',
        'operation_type': 'morte',
    }
    return render(request, 'operations/occurrence_form.html', context)


@login_required
def abate_create_view(request):
    """Registra abate"""
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
                        'peso': str(form.cleaned_data.get('peso', '')) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, f'Abate registrado com sucesso!')
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar abate: {e}')
    else:
        form = AbateForm()
    
    context = {
        'form': form,
        'title': 'Registrar Abate',
        'operation_type': 'abate',
    }
    return render(request, 'operations/occurrence_form.html', context)


@login_required
def venda_create_view(request):
    """Registra venda"""
    if request.method == 'POST':
        form = VendaForm(request.POST)
        if form.is_valid():
            try:
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                    'peso': str(form.cleaned_data.get('peso')) if form.cleaned_data.get('peso') else None,
                    'preco_total': str(form.cleaned_data.get('preco_total', '')) if form.cleaned_data.get('preco_total') else None,
                }
                
                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.VENDA,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    client_id=str(form.cleaned_data['client'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, f'Venda registrada com sucesso!')
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar venda: {e}')
    else:
        form = VendaForm()
    
    context = {
        'form': form,
        'title': 'Registrar Venda',
        'operation_type': 'venda',
    }
    return render(request, 'operations/occurrence_form.html', context)


@login_required
def doacao_create_view(request):
    """Registra doação"""
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
                        'peso': str(form.cleaned_data.get('peso', '')) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, f'Doação registrada com sucesso!')
                return redirect('ocorrencias:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar doação: {e}')
    else:
        form = DoacaoForm()
    
    context = {
        'form': form,
        'title': 'Registrar Doação',
        'operation_type': 'doacao',
    }
    return render(request, 'operations/occurrence_form.html', context)
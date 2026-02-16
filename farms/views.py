"""
Farms Views.

MELHORIAS:
  - @login_required em todas as views
  - Busca por nome na listagem
  - deactivate/activate aceitam somente POST (modal confirma antes de enviar)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q

from .models import Farm
from .forms import FarmForm
from inventory.services import StockQueryService


@login_required
def farm_list_view(request):
    """Lista fazendas ativas com busca."""
    search = request.GET.get('q', '').strip()

    farms = Farm.objects.filter(is_active=True).order_by('name')

    if search:
        farms = farms.filter(Q(name__icontains=search))

    farms_with_summary = []
    for farm in farms:
        summary       = StockQueryService.get_farm_stock_summary(str(farm.id))
        total_animals = sum(item['quantidade'] for item in summary)
        farms_with_summary.append({
            'farm':          farm,
            'total_animals': total_animals,
            'summary':       summary,
        })

    context = {
        'farms_with_summary': farms_with_summary,
        'search_term':        search,
        'total_count':        len(farms_with_summary),
    }
    return render(request, 'farms/farm_list.html', context)


@login_required
def farm_create_view(request):
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                farm = form.save()
                messages.success(
                    request,
                    f'✅ Fazenda "{farm.name}" cadastrada com sucesso! '
                    f'Saldos inicializados automaticamente.'
                )
            return redirect('farms:list')
    else:
        form = FarmForm()

    return render(request, 'farms/farm_form.html', {
        'form': form, 'title': 'Nova Fazenda', 'button_text': 'Cadastrar',
    })


@login_required
def farm_update_view(request, pk):
    farm = get_object_or_404(Farm, pk=pk)

    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)
        if form.is_valid():
            farm = form.save()
            messages.success(request, f'✅ Fazenda "{farm.name}" atualizada com sucesso!')
            return redirect('farms:list')
    else:
        form = FarmForm(instance=farm)

    return render(request, 'farms/farm_form.html', {
        'form': form, 'title': f'Editar: {farm.name}',
        'button_text': 'Salvar', 'farm': farm,
    })


@login_required
def farm_detail_view(request, pk):
    farm = get_object_or_404(Farm, pk=pk)

    summary       = StockQueryService.get_farm_stock_summary(str(farm.id))
    total_animals = sum(item['quantidade'] for item in summary)
    history       = StockQueryService.get_movement_history(farm_id=str(farm.id), limit=20)

    return render(request, 'farms/farm_detail.html', {
        'farm': farm, 'summary': summary,
        'total_animals': total_animals, 'history': history,
    })


@login_required
def farm_deactivate_view(request, pk):
    """Desativa fazenda. Aceita apenas POST (confirmação via modal no front-end)."""
    farm = get_object_or_404(Farm, pk=pk)

    if request.method == 'POST':
        farm.deactivate()
        messages.warning(request, f'Fazenda "{farm.name}" desativada.')
        return redirect('farms:list')

    # GET: fallback para página de confirmação (caso o usuário acesse diretamente)
    return render(request, 'farms/farm_confirm.html', {
        'farm': farm, 'action': 'desativar',
    })


@login_required
def farm_activate_view(request, pk):
    """Reativa fazenda. Aceita apenas POST."""
    farm = get_object_or_404(Farm, pk=pk)

    if request.method == 'POST':
        farm.activate()
        messages.success(request, f'Fazenda "{farm.name}" reativada.')
        return redirect('farms:list')

    return render(request, 'farms/farm_confirm.html', {
        'farm': farm, 'action': 'reativar',
    })
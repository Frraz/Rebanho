"""
Farms Views - Views de gerenciamento de fazendas.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from .models import Farm
from .forms import FarmForm
from inventory.services import StockQueryService


def farm_list_view(request):
    """Lista todas as fazendas ativas"""
    farms = Farm.objects.filter(is_active=True).order_by('name')
    
    # Adicionar resumo de saldo para cada fazenda
    farms_with_summary = []
    for farm in farms:
        summary = StockQueryService.get_farm_stock_summary(str(farm.id))
        total_animals = sum(item['quantidade'] for item in summary)
        farms_with_summary.append({
            'farm': farm,
            'total_animals': total_animals,
            'summary': summary,
        })
    
    context = {
        'farms_with_summary': farms_with_summary,
    }
    return render(request, 'farms/farm_list.html', context)


def farm_create_view(request):
    """Cria nova fazenda"""
    if request.method == 'POST':
        form = FarmForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                farm = form.save()
                messages.success(
                    request,
                    f'Fazenda "{farm.name}" cadastrada com sucesso! '
                    f'Saldos inicializados automaticamente.'
                )
            return redirect('farms:list')
    else:
        form = FarmForm()
    
    context = {
        'form': form,
        'title': 'Nova Fazenda',
        'button_text': 'Cadastrar',
    }
    return render(request, 'farms/farm_form.html', context)


def farm_update_view(request, pk):
    """Edita fazenda existente"""
    farm = get_object_or_404(Farm, pk=pk)
    
    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)
        if form.is_valid():
            farm = form.save()
            messages.success(request, f'Fazenda "{farm.name}" atualizada com sucesso!')
            return redirect('farms:list')
    else:
        form = FarmForm(instance=farm)
    
    context = {
        'form': form,
        'title': f'Editar: {farm.name}',
        'button_text': 'Salvar',
        'farm': farm,
    }
    return render(request, 'farms/farm_form.html', context)


def farm_detail_view(request, pk):
    """Detalha fazenda com saldos por categoria"""
    farm = get_object_or_404(Farm, pk=pk)
    
    # Obter resumo de saldos
    summary = StockQueryService.get_farm_stock_summary(str(farm.id))
    total_animals = sum(item['quantidade'] for item in summary)
    
    # Obter histórico recente de movimentações
    history = StockQueryService.get_movement_history(
        farm_id=str(farm.id),
        limit=20
    )
    
    context = {
        'farm': farm,
        'summary': summary,
        'total_animals': total_animals,
        'history': history,
    }
    return render(request, 'farms/farm_detail.html', context)


def farm_deactivate_view(request, pk):
    """Desativa fazenda (soft delete)"""
    farm = get_object_or_404(Farm, pk=pk)
    
    if request.method == 'POST':
        farm.deactivate()
        messages.warning(request, f'Fazenda "{farm.name}" desativada.')
        return redirect('farms:list')
    
    context = {
        'farm': farm,
        'action': 'desativar',
    }
    return render(request, 'farms/farm_confirm.html', context)


def farm_activate_view(request, pk):
    """Reativa fazenda"""
    farm = get_object_or_404(Farm, pk=pk)
    
    if request.method == 'POST':
        farm.activate()
        messages.success(request, f'Fazenda "{farm.name}" reativada.')
        return redirect('farms:list')
    
    context = {
        'farm': farm,
        'action': 'reativar',
    }
    return render(request, 'farms/farm_confirm.html', context)
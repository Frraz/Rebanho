"""
Inventory Cadastros Views - Tipos de Animal.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from inventory.models import AnimalCategory
from inventory.forms import AnimalCategoryForm


def animal_category_list_view(request):
    """Lista todas as categorias de animais ativas"""
    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
    
    context = {
        'categories': categories,
    }
    return render(request, 'inventory/category_list.html', context)


def animal_category_create_view(request):
    """Cria nova categoria"""
    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                category = form.save()
                messages.success(
                    request,
                    f'Tipo de animal "{category.name}" cadastrado com sucesso! '
                    f'Saldos criados automaticamente para todas as fazendas.'
                )
            return redirect('inventory_cadastros:category_list')
    else:
        form = AnimalCategoryForm()
    
    context = {
        'form': form,
        'title': 'Novo Tipo de Animal',
        'button_text': 'Cadastrar',
    }
    return render(request, 'inventory/category_form.html', context)


def animal_category_update_view(request, pk):
    """Edita categoria existente"""
    category = get_object_or_404(AnimalCategory, pk=pk)
    
    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Tipo de animal "{category.name}" atualizado!')
            return redirect('inventory_cadastros:category_list')
    else:
        form = AnimalCategoryForm(instance=category)
    
    context = {
        'form': form,
        'title': f'Editar: {category.name}',
        'button_text': 'Salvar',
        'category': category,
    }
    return render(request, 'inventory/category_form.html', context)


def animal_category_deactivate_view(request, pk):
    """Desativa categoria (soft delete)"""
    category = get_object_or_404(AnimalCategory, pk=pk)
    
    if request.method == 'POST':
        category.deactivate()
        messages.warning(request, f'Tipo de animal "{category.name}" desativado.')
        return redirect('inventory_cadastros:category_list')
    
    context = {
        'category': category,
        'action': 'desativar',
    }
    return render(request, 'inventory/category_confirm.html', context)


def animal_category_activate_view(request, pk):
    """Reativa categoria"""
    category = get_object_or_404(AnimalCategory, pk=pk)
    
    if request.method == 'POST':
        category.activate()
        messages.success(request, f'Tipo de animal "{category.name}" reativado.')
        return redirect('inventory_cadastros:category_list')
    
    context = {
        'category': category,
        'action': 'reativar',
    }
    return render(request, 'inventory/category_confirm.html', context)
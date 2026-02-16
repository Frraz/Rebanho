"""
Inventory Cadastros Views - Tipos de Animal.

MELHORIAS:
  - @login_required em todas as views
  - Busca por nome/descrição na listagem
  - deactivate/activate via POST (modal confirma no front-end)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q

from inventory.models import AnimalCategory
from inventory.forms import AnimalCategoryForm


@login_required
def animal_category_list_view(request):
    """Lista categorias ativas com busca por nome."""
    search = request.GET.get('q', '').strip()

    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')

    if search:
        categories = categories.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    context = {
        'categories':  categories,
        'search_term': search,
        'total_count': categories.count(),
    }
    return render(request, 'inventory/category_list.html', context)


@login_required
def animal_category_create_view(request):
    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                category = form.save()
                messages.success(
                    request,
                    f'✅ Tipo "{category.name}" cadastrado! '
                    f'Saldos criados para todas as fazendas automaticamente.'
                )
            return redirect('inventory_cadastros:category_list')
    else:
        form = AnimalCategoryForm()

    return render(request, 'inventory/category_form.html', {
        'form': form, 'title': 'Novo Tipo de Animal', 'button_text': 'Cadastrar',
    })


@login_required
def animal_category_update_view(request, pk):
    category = get_object_or_404(AnimalCategory, pk=pk)

    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST, instance=category)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'✅ Tipo "{category.name}" atualizado!')
            return redirect('inventory_cadastros:category_list')
    else:
        form = AnimalCategoryForm(instance=category)

    return render(request, 'inventory/category_form.html', {
        'form': form, 'title': f'Editar: {category.name}',
        'button_text': 'Salvar', 'category': category,
    })


@login_required
def animal_category_deactivate_view(request, pk):
    """Desativa categoria via POST (modal confirma no front-end)."""
    category = get_object_or_404(AnimalCategory, pk=pk)

    if request.method == 'POST':
        category.deactivate()
        messages.warning(request, f'Tipo de animal "{category.name}" desativado.')
        return redirect('inventory_cadastros:category_list')

    return render(request, 'inventory/category_confirm.html', {
        'category': category, 'action': 'desativar',
    })


@login_required
def animal_category_activate_view(request, pk):
    category = get_object_or_404(AnimalCategory, pk=pk)

    if request.method == 'POST':
        category.activate()
        messages.success(request, f'Tipo de animal "{category.name}" reativado.')
        return redirect('inventory_cadastros:category_list')

    return render(request, 'inventory/category_confirm.html', {
        'category': category, 'action': 'reativar',
    })
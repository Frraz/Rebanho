"""
Inventory Movimentações Views.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required  # ADICIONAR

from inventory.forms import (
    NascimentoForm, DesmameForm, SaldoForm, CompraForm,
    ManejoForm, MudancaCategoriaForm
)
from inventory.services import MovementService, StockQueryService
from operations.services import TransferService
from inventory.domain import OperationType



def movement_list_view(request):
    """Lista histórico de movimentações"""
    from inventory.services import StockQueryService
    
    # Filtros
    farm_id = request.GET.get('farm')
    category_id = request.GET.get('category')
    
    history = StockQueryService.get_movement_history(
        farm_id=farm_id,
        animal_category_id=category_id,
        limit=50
    )
    
    context = {
        'history': history,
    }
    return render(request, 'inventory/movement_list.html', context)


@login_required
def nascimento_create_view(request):
    """Registra nascimento"""
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
                        'peso': str(form.cleaned_data.get('peso', '')) if form.cleaned_data.get('peso') else None,
                    },
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(
                    request,
                    f'Nascimento registrado: {movement.quantity} {movement.farm_stock_balance.animal_category.name}(s) '
                    f'na {movement.farm_stock_balance.farm.name}'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro ao registrar nascimento: {e}')
    else:
        form = NascimentoForm()
    
    context = {
        'form': form,
        'title': 'Registrar Nascimento',
        'operation_type': 'nascimento',
    }
    return render(request, 'inventory/movement_form.html', context)


@login_required 
def desmame_create_view(request):
    """Registra desmame"""
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
                messages.success(request, f'Desmame registrado com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = DesmameForm()
    
    return render(request, 'inventory/movement_form.html', {
        'form': form,
        'title': 'Registrar Desmame',
    })


@login_required
def saldo_create_view(request):
    """Ajuste de saldo"""
    if request.method == 'POST':
        form = SaldoForm(request.POST)
        if form.is_valid():
            try:
                movement = MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.SALDO,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, 'Saldo ajustado com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = SaldoForm()
    
    return render(request, 'inventory/movement_form.html', {
        'form': form,
        'title': 'Ajustar Saldo',
    })


@login_required
def compra_create_view(request):
    """Registra compra"""
    if request.method == 'POST':
        form = CompraForm(request.POST)
        if form.is_valid():
            try:
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                    'peso': str(form.cleaned_data.get('peso', '')) if form.cleaned_data.get('peso') else None,
                    'preco_unitario': str(form.cleaned_data.get('preco_unitario', '')) if form.cleaned_data.get('preco_unitario') else None,
                    'fornecedor': form.cleaned_data.get('fornecedor', ''),
                }
                
                movement = MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.COMPRA,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, 'Compra registrada com sucesso!')
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = CompraForm()
    
    return render(request, 'inventory/movement_form.html', {
        'form': form,
        'title': 'Registrar Compra',
    })


@login_required
def manejo_create_view(request):
    """Registra manejo (transferência entre fazendas)"""
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
                    f'Manejo executado: {saida.quantity} {saida.farm_stock_balance.animal_category.name}(s) '
                    f'transferidos de {saida.farm_stock_balance.farm.name} '
                    f'para {entrada.farm_stock_balance.farm.name}'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = ManejoForm()
    
    return render(request, 'inventory/movement_form.html', {
        'form': form,
        'title': 'Registrar Manejo',
    })


@login_required
def mudanca_categoria_create_view(request):
    """Registra mudança de categoria"""
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
                    f'Mudança de categoria executada: {saida.quantity} '
                    f'{saida.farm_stock_balance.animal_category.name}(s) '
                    f'→ {entrada.farm_stock_balance.animal_category.name}(s)'
                )
                return redirect('movimentacoes:list')
            except Exception as e:
                messages.error(request, f'Erro: {e}')
    else:
        form = MudancaCategoriaForm()
    
    return render(request, 'inventory/movement_form.html', {
        'form': form,
        'title': 'Mudança de Categoria',
    })
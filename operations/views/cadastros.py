"""
Operations Cadastros Views - Clientes e Tipos de Morte.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from operations.models import Client, DeathReason
from operations.forms import ClientForm, DeathReasonForm


# ==============================================================================
# CLIENTES
# ==============================================================================

def client_list_view(request):
    """Lista todos os clientes ativos"""
    clients = Client.objects.filter(is_active=True).order_by('name')
    
    context = {
        'clients': clients,
    }
    return render(request, 'operations/client_list.html', context)


def client_create_view(request):
    """Cria novo cliente"""
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Cliente "{client.name}" cadastrado com sucesso!')
            return redirect('operations_cadastros:client_list')
    else:
        form = ClientForm()
    
    context = {
        'form': form,
        'title': 'Novo Cliente',
        'button_text': 'Cadastrar',
    }
    return render(request, 'operations/client_form.html', context)


def client_update_view(request, pk):
    """Edita cliente existente"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'Cliente "{client.name}" atualizado com sucesso!')
            return redirect('operations_cadastros:client_list')
    else:
        form = ClientForm(instance=client)
    
    context = {
        'form': form,
        'title': f'Editar: {client.name}',
        'button_text': 'Salvar',
        'client': client,
    }
    return render(request, 'operations/client_form.html', context)


def client_deactivate_view(request, pk):
    """Desativa cliente (soft delete)"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        client.deactivate()
        messages.warning(request, f'Cliente "{client.name}" desativado.')
        return redirect('operations_cadastros:client_list')
    
    context = {
        'client': client,
        'action': 'desativar',
    }
    return render(request, 'operations/client_confirm.html', context)


def client_activate_view(request, pk):
    """Reativa cliente"""
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        client.activate()
        messages.success(request, f'Cliente "{client.name}" reativado.')
        return redirect('operations_cadastros:client_list')
    
    context = {
        'client': client,
        'action': 'reativar',
    }
    return render(request, 'operations/client_confirm.html', context)


# ==============================================================================
# TIPOS DE MORTE
# ==============================================================================

def death_reason_list_view(request):
    """Lista todos os tipos de morte ativos"""
    reasons = DeathReason.objects.filter(is_active=True).order_by('name')
    
    context = {
        'reasons': reasons,
    }
    return render(request, 'operations/death_reason_list.html', context)


def death_reason_create_view(request):
    """Cria novo tipo de morte"""
    if request.method == 'POST':
        form = DeathReasonForm(request.POST)
        if form.is_valid():
            reason = form.save()
            messages.success(request, f'Tipo de morte "{reason.name}" cadastrado com sucesso!')
            return redirect('operations_cadastros:death_reason_list')
    else:
        form = DeathReasonForm()
    
    context = {
        'form': form,
        'title': 'Novo Tipo de Morte',
        'button_text': 'Cadastrar',
    }
    return render(request, 'operations/death_reason_form.html', context)


def death_reason_update_view(request, pk):
    """Edita tipo de morte existente"""
    reason = get_object_or_404(DeathReason, pk=pk)
    
    if request.method == 'POST':
        form = DeathReasonForm(request.POST, instance=reason)
        if form.is_valid():
            reason = form.save()
            messages.success(request, f'Tipo de morte "{reason.name}" atualizado com sucesso!')
            return redirect('operations_cadastros:death_reason_list')
    else:
        form = DeathReasonForm(instance=reason)
    
    context = {
        'form': form,
        'title': f'Editar: {reason.name}',
        'button_text': 'Salvar',
        'reason': reason,
    }
    return render(request, 'operations/death_reason_form.html', context)


def death_reason_deactivate_view(request, pk):
    """Desativa tipo de morte (soft delete)"""
    reason = get_object_or_404(DeathReason, pk=pk)
    
    if request.method == 'POST':
        reason.deactivate()
        messages.warning(request, f'Tipo de morte "{reason.name}" desativado.')
        return redirect('operations_cadastros:death_reason_list')
    
    context = {
        'reason': reason,
        'action': 'desativar',
    }
    return render(request, 'operations/death_reason_confirm.html', context)


def death_reason_activate_view(request, pk):
    """Reativa tipo de morte"""
    reason = get_object_or_404(DeathReason, pk=pk)
    
    if request.method == 'POST':
        reason.activate()
        messages.success(request, f'Tipo de morte "{reason.name}" reativado.')
        return redirect('operations_cadastros:death_reason_list')
    
    context = {
        'reason': reason,
        'action': 'reativar',
    }
    return render(request, 'operations/death_reason_confirm.html', context)
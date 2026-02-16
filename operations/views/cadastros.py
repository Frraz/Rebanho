"""
Operations Cadastros Views - Clientes e Tipos de Morte.

MELHORIAS:
  - @login_required em todas as views
  - Busca por nome/CPF/CNPJ em clientes
  - Busca por nome/descrição em tipos de morte
  - deactivate/activate via POST (modal confirma no front-end)
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from operations.models import Client, DeathReason
from operations.forms import ClientForm, DeathReasonForm


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def client_list_view(request):
    """Lista clientes ativos com busca por nome ou CPF/CNPJ."""
    search = request.GET.get('q', '').strip()

    clients = Client.objects.filter(is_active=True).order_by('name')

    if search:
        clients = clients.filter(
            Q(name__icontains=search)
            | Q(cpf_cnpj__icontains=search)
            | Q(phone__icontains=search)
            | Q(email__icontains=search)
        )

    context = {
        'clients':     clients,
        'search_term': search,
        'total_count': clients.count(),
    }
    return render(request, 'operations/client_list.html', context)


@login_required
def client_create_view(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'✅ Cliente "{client.name}" cadastrado com sucesso!')
            return redirect('operations_cadastros:client_list')
    else:
        form = ClientForm()

    return render(request, 'operations/client_form.html', {
        'form': form, 'title': 'Novo Cliente', 'button_text': 'Cadastrar',
    })


@login_required
def client_update_view(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            messages.success(request, f'✅ Cliente "{client.name}" atualizado!')
            return redirect('operations_cadastros:client_list')
    else:
        form = ClientForm(instance=client)

    return render(request, 'operations/client_form.html', {
        'form': form, 'title': f'Editar: {client.name}',
        'button_text': 'Salvar', 'client': client,
    })


@login_required
def client_deactivate_view(request, pk):
    """Desativa cliente via POST (modal confirma no front-end)."""
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.deactivate()
        messages.warning(request, f'Cliente "{client.name}" desativado.')
        return redirect('operations_cadastros:client_list')

    return render(request, 'operations/client_confirm.html', {
        'client': client, 'action': 'desativar',
    })


@login_required
def client_activate_view(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.activate()
        messages.success(request, f'Cliente "{client.name}" reativado.')
        return redirect('operations_cadastros:client_list')

    return render(request, 'operations/client_confirm.html', {
        'client': client, 'action': 'reativar',
    })


# ══════════════════════════════════════════════════════════════════════════════
# TIPOS DE MORTE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def death_reason_list_view(request):
    """Lista tipos de morte ativos com busca por nome/descrição."""
    search = request.GET.get('q', '').strip()

    reasons = DeathReason.objects.filter(is_active=True).order_by('name')

    if search:
        reasons = reasons.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )

    context = {
        'reasons':     reasons,
        'search_term': search,
        'total_count': reasons.count(),
    }
    return render(request, 'operations/death_reason_list.html', context)


@login_required
def death_reason_create_view(request):
    if request.method == 'POST':
        form = DeathReasonForm(request.POST)
        if form.is_valid():
            reason = form.save()
            messages.success(request, f'✅ Tipo de morte "{reason.name}" cadastrado!')
            return redirect('operations_cadastros:death_reason_list')
    else:
        form = DeathReasonForm()

    return render(request, 'operations/death_reason_form.html', {
        'form': form, 'title': 'Novo Tipo de Morte', 'button_text': 'Cadastrar',
    })


@login_required
def death_reason_update_view(request, pk):
    reason = get_object_or_404(DeathReason, pk=pk)

    if request.method == 'POST':
        form = DeathReasonForm(request.POST, instance=reason)
        if form.is_valid():
            reason = form.save()
            messages.success(request, f'✅ Tipo de morte "{reason.name}" atualizado!')
            return redirect('operations_cadastros:death_reason_list')
    else:
        form = DeathReasonForm(instance=reason)

    return render(request, 'operations/death_reason_form.html', {
        'form': form, 'title': f'Editar: {reason.name}',
        'button_text': 'Salvar', 'reason': reason,
    })


@login_required
def death_reason_deactivate_view(request, pk):
    """Desativa tipo de morte via POST (modal confirma no front-end)."""
    reason = get_object_or_404(DeathReason, pk=pk)

    if request.method == 'POST':
        reason.deactivate()
        messages.warning(request, f'Tipo de morte "{reason.name}" desativado.')
        return redirect('operations_cadastros:death_reason_list')

    return render(request, 'operations/death_reason_confirm.html', {
        'reason': reason, 'action': 'desativar',
    })


@login_required
def death_reason_activate_view(request, pk):
    reason = get_object_or_404(DeathReason, pk=pk)

    if request.method == 'POST':
        reason.activate()
        messages.success(request, f'Tipo de morte "{reason.name}" reativado.')
        return redirect('operations_cadastros:death_reason_list')

    return render(request, 'operations/death_reason_confirm.html', {
        'reason': reason, 'action': 'reativar',
    })
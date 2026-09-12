"""
finance/views/ajustes.py

Ajuste manual de saldo — um crédito ou débito avulso no extrato do cliente.

Existe para o que a operação normal não cobre: perdoar uma dívida, corrigir um
lançamento antigo, registrar um acerto feito fora do sistema. Por isso o motivo
é obrigatório.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from finance.forms import AdjustmentForm
from finance.models import EntrySource, FinancialEntry
from finance.services import AdjustmentService, BalanceService
from finance.utils.money import to_pt_br_input

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def ajuste_create_view(request):
    if request.method == 'POST':
        form = AdjustmentForm(request.POST)
        if form.is_valid():
            try:
                AdjustmentService.create(
                    client=form.cleaned_data['client'],
                    date=form.cleaned_data['date'],
                    entry_type=form.cleaned_data['entry_type'],
                    amount=form.cleaned_data['amount'],
                    description=form.cleaned_data['description'],
                    user=request.user,
                )
                cliente = form.cleaned_data['client']
                messages.success(request, _mensagem(cliente, 'registrado'))
                return redirect('relatorios_financeiros:saldos')
            except ValidationError as exc:
                messages.error(request, _texto_erro(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao registrar ajuste: %s", exc, exc_info=True)
                messages.error(request, f"Erro ao registrar o ajuste: {exc}")
    else:
        form = AdjustmentForm(initial={'client': request.GET.get('cliente') or None})

    return render(request, 'finance/ajuste_form.html', {
        'form': form,
        'titulo': 'Ajuste Manual de Saldo',
        'descricao': 'Lance um crédito ou débito avulso no extrato de um cliente',
        'botao': 'Registrar Ajuste',
        'cancel_url': reverse('relatorios_financeiros:saldos'),
        'ajuste': None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def ajuste_edit_view(request, pk):
    ajuste = get_object_or_404(
        FinancialEntry.objects.select_related('client'),
        pk=pk, source_type=EntrySource.AJUSTE,
    )

    if request.method == 'POST':
        form = AdjustmentForm(request.POST)
        if form.is_valid():
            try:
                AdjustmentService.update(
                    entry=ajuste,
                    client=form.cleaned_data['client'],
                    date=form.cleaned_data['date'],
                    entry_type=form.cleaned_data['entry_type'],
                    amount=form.cleaned_data['amount'],
                    description=form.cleaned_data['description'],
                    user=request.user,
                )
                messages.success(request, _mensagem(form.cleaned_data['client'], 'atualizado'))
                return redirect('relatorios_financeiros:fluxo')
            except ValidationError as exc:
                messages.error(request, _texto_erro(exc))
    else:
        form = AdjustmentForm(initial={
            'client': ajuste.client_id,
            'date': ajuste.date,
            'entry_type': ajuste.entry_type,
            'amount': to_pt_br_input(ajuste.amount),
            'description': ajuste.description,
        })

    return render(request, 'finance/ajuste_form.html', {
        'form': form,
        'titulo': 'Editar Ajuste',
        'descricao': f"Ajuste de {ajuste.client.name} em {ajuste.date:%d/%m/%Y}",
        'botao': 'Salvar Alterações',
        'cancel_url': reverse('relatorios_financeiros:fluxo'),
        'ajuste': ajuste,
    })


@login_required
@require_POST
def ajuste_delete_view(request, pk):
    ajuste = get_object_or_404(
        FinancialEntry.objects.select_related('client'),
        pk=pk, source_type=EntrySource.AJUSTE,
    )
    try:
        resumo = AdjustmentService.delete(
            entry=ajuste,
            user=request.user,
            reason=request.POST.get('reason', '').strip(),
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(
            request,
            f"Ajuste de {resumo['cliente']} apagado. O saldo foi recalculado."
        )
    except ValidationError as exc:
        messages.error(request, _texto_erro(exc))

    return redirect(request.POST.get('next') or reverse('relatorios_financeiros:fluxo'))


def _mensagem(cliente, verbo):
    from finance.templatetags.finance_tags import moeda_rs, saldo_rotulo

    saldo = BalanceService.get_balance(cliente.id)
    return (
        f"Ajuste {verbo} para {cliente.name}. "
        f"Saldo agora: {moeda_rs(abs(saldo))} ({saldo_rotulo(saldo).lower()})."
    )


def _texto_erro(exc):
    if hasattr(exc, 'message'):
        return exc.message
    if hasattr(exc, 'messages') and exc.messages:
        return ' '.join(exc.messages)
    return str(exc)

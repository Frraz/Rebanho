"""
finance/views/pagamentos.py

Telas de pagamento: lista com filtros, cadastro, edição, exclusão e PDF.
"""
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from finance.filters import aplicar_periodo, contexto_periodo, parse_periodo, rotulo_periodo
from finance.forms import PaymentForm
from finance.models import Payment, PaymentType
from finance.services import BalanceService, PaymentService
from finance.utils.money import to_pt_br_input
from finance.views.pdf import render_pdf
from operations.models import Client

logger = logging.getLogger(__name__)

POR_PAGINA = 25


def _ler_filtros(request):
    return {
        'busca': request.GET.get('q', '').strip(),
        'cliente_id': request.GET.get('cliente', '').strip(),
        'tipo': request.GET.get('tipo', '').strip(),
        'periodo': parse_periodo(request),
    }


def _aplicar_filtros(queryset, filtros):
    queryset = aplicar_periodo(queryset, filtros['periodo'], campo='date')

    if filtros['cliente_id']:
        queryset = queryset.filter(client_id=filtros['cliente_id'])

    if filtros['tipo'] in dict(PaymentType.choices):
        queryset = queryset.filter(payment_type=filtros['tipo'])

    if filtros['busca']:
        queryset = queryset.filter(
            Q(client__name__icontains=filtros['busca'])
            | Q(description__icontains=filtros['busca'])
        )

    return queryset


def _tem_filtros(filtros):
    return any([
        filtros['busca'], filtros['cliente_id'], filtros['tipo'],
        filtros['periodo']['tem_periodo'],
    ])


def _queryset_base():
    return (
        Payment.objects
        .select_related('client', 'created_by')
        .order_by('-date', '-created_at')
    )


def _contexto_filtros(filtros):
    contexto = {
        'busca': filtros['busca'],
        'cliente_filtro': filtros['cliente_id'],
        'tipo_filtro': filtros['tipo'],
        'filtros_ativos': _tem_filtros(filtros),
        'clientes': Client.objects.filter(is_active=True).order_by('name'),
        'tipos': PaymentType.choices,
    }
    contexto.update(contexto_periodo(filtros['periodo']))
    return contexto


# ══════════════════════════════════════════════════════════════════════════════
# LISTA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def pagamento_list_view(request):
    filtros = _ler_filtros(request)
    queryset = _aplicar_filtros(_queryset_base(), filtros)

    total_periodo = queryset.aggregate(valor=Sum('amount'))['valor']

    paginator = Paginator(queryset, POR_PAGINA)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    params = request.GET.copy()
    params.pop('page', None)
    codificado = params.urlencode()

    contexto = {
        'page_obj': page_obj,
        'paginator': paginator,
        'total_count': paginator.count,
        'total_periodo': total_periodo,
        'querystring': f'&{codificado}' if codificado else '',
    }
    contexto.update(_contexto_filtros(filtros))
    return render(request, 'finance/pagamento_list.html', contexto)


# ══════════════════════════════════════════════════════════════════════════════
# CADASTRO E EDIÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def pagamento_create_view(request):
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                pagamento = PaymentService.create(
                    client=form.cleaned_data['client'],
                    date=form.cleaned_data['date'],
                    amount=form.cleaned_data['amount'],
                    payment_type=form.cleaned_data['payment_type'],
                    description=form.cleaned_data.get('description', ''),
                    user=request.user,
                )
                messages.success(request, _mensagem(pagamento, 'registrado'))
                return redirect('pagamentos:list')
            except ValidationError as exc:
                messages.error(request, _texto_erro(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao registrar pagamento: %s", exc, exc_info=True)
                messages.error(request, f"Erro ao registrar o pagamento: {exc}")
    else:
        form = PaymentForm()

    return render(request, 'finance/pagamento_form.html', {
        'form': form,
        'titulo': 'Novo Pagamento',
        'descricao': 'Registre um pagamento recebido de um cliente',
        'botao': 'Registrar Pagamento',
        'cancel_url': reverse('pagamentos:list'),
        'pagamento': None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def pagamento_edit_view(request, pk):
    pagamento = get_object_or_404(Payment.objects.select_related('client'), pk=pk)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            try:
                pagamento = PaymentService.update(
                    payment=pagamento,
                    client=form.cleaned_data['client'],
                    date=form.cleaned_data['date'],
                    amount=form.cleaned_data['amount'],
                    payment_type=form.cleaned_data['payment_type'],
                    description=form.cleaned_data.get('description', ''),
                    user=request.user,
                )
                messages.success(request, _mensagem(pagamento, 'atualizado'))
                return redirect('pagamentos:list')
            except ValidationError as exc:
                messages.error(request, _texto_erro(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao editar pagamento %s: %s", pk, exc, exc_info=True)
                messages.error(request, f"Erro ao atualizar o pagamento: {exc}")
    else:
        form = PaymentForm(initial={
            'client': pagamento.client_id,
            'date': pagamento.date,
            'amount': to_pt_br_input(pagamento.amount),
            'payment_type': pagamento.payment_type,
            'description': pagamento.description,
        })

    return render(request, 'finance/pagamento_form.html', {
        'form': form,
        'titulo': 'Editar Pagamento',
        'descricao': f"Pagamento de {pagamento.client.name} em {pagamento.date:%d/%m/%Y}",
        'botao': 'Salvar Alterações',
        'cancel_url': reverse('pagamentos:list'),
        'pagamento': pagamento,
    })


@login_required
@require_POST
def pagamento_delete_view(request, pk):
    pagamento = get_object_or_404(Payment.objects.select_related('client'), pk=pk)
    motivo = request.POST.get('reason', '').strip()

    try:
        resumo = PaymentService.delete(
            payment=pagamento,
            user=request.user,
            reason=motivo,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(
            request,
            f"Pagamento de {resumo['cliente']} em {resumo['data']:%d/%m/%Y} apagado. "
            f"O crédito saiu do saldo do cliente."
        )
    except ValidationError as exc:
        messages.error(request, _texto_erro(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao apagar pagamento %s: %s", pk, exc, exc_info=True)
        messages.error(request, f"Erro ao apagar o pagamento: {exc}")

    return redirect(request.POST.get('next') or reverse('pagamentos:list'))


# ══════════════════════════════════════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def pagamento_pdf_view(request):
    filtros = _ler_filtros(request)
    queryset = _aplicar_filtros(_queryset_base(), filtros)

    partes = []
    if filtros['cliente_id']:
        cliente = Client.objects.filter(pk=filtros['cliente_id']).first()
        if cliente:
            partes.append(f"Cliente: {cliente.name}")
    if filtros['tipo']:
        partes.append(f"Tipo: {dict(PaymentType.choices).get(filtros['tipo'])}")
    if filtros['busca']:
        partes.append(f"Busca: \"{filtros['busca']}\"")

    return render_pdf(
        'finance/pdf/pagamento_list_pdf.html',
        {
            'pagamentos': queryset[:3000],
            'total_count': queryset.count(),
            'total_periodo': queryset.aggregate(valor=Sum('amount'))['valor'],
            'periodo_label': rotulo_periodo(filtros['periodo']),
            'resumo_filtros': ' · '.join(partes),
            'user': request.user,
        },
        nome_arquivo='pagamentos',
    )


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _mensagem(pagamento, verbo):
    from finance.templatetags.finance_tags import moeda_rs, saldo_rotulo

    saldo = BalanceService.get_balance(pagamento.client_id)
    return (
        f"Pagamento {verbo}: {moeda_rs(pagamento.amount)} de {pagamento.client.name}. "
        f"Saldo agora: {moeda_rs(abs(saldo))} ({saldo_rotulo(saldo).lower()})."
    )


def _texto_erro(exc):
    if hasattr(exc, 'message'):
        return exc.message
    if hasattr(exc, 'messages') and exc.messages:
        return ' '.join(exc.messages)
    return str(exc)

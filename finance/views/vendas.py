"""
finance/views/vendas.py

Telas de venda: lista com filtros, cadastro multi-lote, edição, exclusão e PDF.

A rota `/ocorrencias/venda/` — que antes abria direto o formulário — passa a
abrir a LISTA, como o cliente pediu. O link do menu não muda.
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

from farms.models import Farm
from finance.filters import aplicar_periodo, contexto_periodo, parse_periodo, rotulo_periodo
from finance.forms import SaleForm, SaleItemFormSet
from finance.models import Sale, SaleStatus
from finance.services import SaleService
from finance.utils.money import to_pt_br_input
from finance.views.pdf import render_pdf
from inventory.domain.exceptions import DomainException
from inventory.models import AnimalCategory
from operations.models import Client

logger = logging.getLogger(__name__)

POR_PAGINA = 25


# ══════════════════════════════════════════════════════════════════════════════
# FILTROS
# ══════════════════════════════════════════════════════════════════════════════

def _ler_filtros(request):
    """Lê todos os filtros da tela de vendas de uma vez."""
    periodo = parse_periodo(request)
    return {
        'busca': request.GET.get('q', '').strip(),
        'cliente_id': request.GET.get('cliente', '').strip(),
        'fazenda_id': request.GET.get('fazenda', '').strip(),
        'categoria_id': request.GET.get('categoria', '').strip(),
        'situacao': request.GET.get('situacao', '').strip(),
        'sem_valor': request.GET.get('sem_valor', '').strip(),
        'periodo': periodo,
    }


def _aplicar_filtros(queryset, filtros):
    periodo = filtros['periodo']
    queryset = aplicar_periodo(queryset, periodo, campo='date')

    if filtros['cliente_id']:
        queryset = queryset.filter(client_id=filtros['cliente_id'])

    if filtros['fazenda_id']:
        queryset = queryset.filter(farm_id=filtros['fazenda_id'])

    if filtros['categoria_id']:
        # Uma venda entra no resultado se QUALQUER lote for do tipo escolhido.
        queryset = queryset.filter(items__animal_category_id=filtros['categoria_id'])

    if filtros['situacao'] in (SaleStatus.ATIVA, SaleStatus.CANCELADA):
        queryset = queryset.filter(status=filtros['situacao'])

    if filtros['sem_valor'] == '1':
        # As vendas importadas do histórico que ainda estão sem preço — é por
        # aqui que o usuário as encontra para completar.
        queryset = queryset.filter(Q(total_amount__isnull=True) | Q(total_amount=0))

    if filtros['busca']:
        termo = filtros['busca']
        queryset = queryset.filter(
            Q(client__name__icontains=termo)
            | Q(farm__name__icontains=termo)
            | Q(notes__icontains=termo)
            | Q(items__animal_category__name__icontains=termo)
        )

    # `items__` pode multiplicar linhas no JOIN.
    return queryset.distinct()


def _tem_filtros(filtros):
    return any([
        filtros['busca'], filtros['cliente_id'], filtros['fazenda_id'],
        filtros['categoria_id'], filtros['situacao'], filtros['sem_valor'],
        filtros['periodo']['tem_periodo'],
    ])


def _queryset_base():
    return (
        Sale.objects
        .select_related('client', 'farm', 'created_by')
        .prefetch_related('items__animal_category')
        .order_by('-date', '-created_at')
    )


def _contexto_filtros(request, filtros):
    """Dados para redesenhar o painel de filtros."""
    contexto = {
        'busca': filtros['busca'],
        'cliente_filtro': filtros['cliente_id'],
        'fazenda_filtro': filtros['fazenda_id'],
        'categoria_filtro': filtros['categoria_id'],
        'situacao_filtro': filtros['situacao'],
        'sem_valor_filtro': filtros['sem_valor'],
        'filtros_ativos': _tem_filtros(filtros),
        'fazendas': Farm.objects.filter(is_active=True).order_by('name'),
        'categorias': AnimalCategory.objects.filter(is_active=True).order_by(
            'display_order', 'name'
        ),
        'clientes': Client.objects.filter(is_active=True).order_by('name'),
        'situacoes': SaleStatus.choices,
    }
    contexto.update(contexto_periodo(filtros['periodo']))
    return contexto


# ══════════════════════════════════════════════════════════════════════════════
# LISTA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def venda_list_view(request):
    filtros = _ler_filtros(request)
    queryset = _aplicar_filtros(_queryset_base(), filtros)

    totais = queryset.aggregate(
        valor=Sum('total_amount'),
        animais=Sum('total_quantity'),
        peso=Sum('total_weight'),
    )

    paginator = Paginator(queryset, POR_PAGINA)
    try:
        page_obj = paginator.page(request.GET.get('page', 1))
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    contexto = {
        'page_obj': page_obj,
        'paginator': paginator,
        'total_count': paginator.count,
        'totais': totais,
        'querystring': _querystring_sem_pagina(request),
    }
    contexto.update(_contexto_filtros(request, filtros))
    return render(request, 'finance/venda_list.html', contexto)


def _querystring_sem_pagina(request):
    """Preserva os filtros nos links de paginação."""
    params = request.GET.copy()
    params.pop('page', None)
    codificado = params.urlencode()
    return f'&{codificado}' if codificado else ''


# ══════════════════════════════════════════════════════════════════════════════
# CADASTRO E EDIÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def venda_create_view(request):
    if request.method == 'POST':
        form = SaleForm(request.POST)
        formset = SaleItemFormSet(request.POST, prefix='itens')

        if form.is_valid() and formset.is_valid():
            try:
                venda = SaleService.create(
                    client=form.cleaned_data['client'],
                    farm=form.cleaned_data['farm'],
                    date=form.cleaned_data['date'],
                    notes=form.cleaned_data.get('notes', ''),
                    items=formset.linhas_validas,
                    user=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, _mensagem_sucesso(venda, 'registrada'))
                return redirect('vendas:list')
            except (ValidationError, DomainException) as exc:
                messages.error(request, _texto_erro(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao registrar venda: %s", exc, exc_info=True)
                messages.error(request, f"Erro ao registrar a venda: {exc}")
    else:
        form = SaleForm()
        formset = SaleItemFormSet(prefix='itens')

    return render(request, 'finance/venda_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Nova Venda',
        'descricao': 'Registre uma venda com um ou mais tipos de animal',
        'botao': 'Registrar Venda',
        'cancel_url': reverse('vendas:list'),
        'venda': None,
    })


@login_required
@require_http_methods(["GET", "POST"])
def venda_edit_view(request, pk):
    venda = get_object_or_404(
        Sale.objects.select_related('client', 'farm').prefetch_related('items'), pk=pk
    )

    if venda.status == SaleStatus.CANCELADA:
        messages.warning(request, "Vendas canceladas não podem ser editadas.")
        return redirect('vendas:list')

    if request.method == 'POST':
        form = SaleForm(request.POST)
        formset = SaleItemFormSet(request.POST, prefix='itens')

        if form.is_valid() and formset.is_valid():
            try:
                venda = SaleService.update(
                    sale=venda,
                    client=form.cleaned_data['client'],
                    farm=form.cleaned_data['farm'],
                    date=form.cleaned_data['date'],
                    notes=form.cleaned_data.get('notes', ''),
                    items=formset.linhas_validas,
                    user=request.user,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )
                messages.success(request, _mensagem_sucesso(venda, 'atualizada'))
                return redirect('vendas:list')
            except (ValidationError, DomainException) as exc:
                messages.error(request, _texto_erro(exc))
            except Exception as exc:  # noqa: BLE001
                logger.error("Erro ao editar venda %s: %s", pk, exc, exc_info=True)
                messages.error(request, f"Erro ao atualizar a venda: {exc}")
    else:
        form = SaleForm(initial={
            'farm': venda.farm_id,
            'client': venda.client_id,
            'date': venda.date,
            'notes': venda.notes,
        })
        # Os valores vão para a tela já em pt-BR. Entregar o Decimal cru faria
        # o preço por quilo (4 casas) ser lido como milhar pela máscara:
        # Decimal("10.0000") viraria "100.000" no campo. Ver finance/utils/money.py.
        formset = SaleItemFormSet(
            prefix='itens',
            initial=[
                {
                    'animal_category': item.animal_category_id,
                    'quantity': item.quantity,
                    'total_weight': to_pt_br_input(item.total_weight),
                    'price_per_kg': to_pt_br_input(item.price_per_kg, casas=4),
                    'total_amount': to_pt_br_input(item.total_amount),
                }
                for item in venda.items.select_related('animal_category').all()
            ],
        )

    return render(request, 'finance/venda_form.html', {
        'form': form,
        'formset': formset,
        'titulo': 'Editar Venda',
        'descricao': f"Venda de {venda.client.name} em {venda.date:%d/%m/%Y}",
        'botao': 'Salvar Alterações',
        'cancel_url': reverse('vendas:list'),
        'venda': venda,
    })


@login_required
@require_POST
def venda_delete_view(request, pk):
    venda = get_object_or_404(Sale.objects.select_related('client'), pk=pk)
    motivo = request.POST.get('reason', '').strip()

    try:
        resumo = SaleService.delete(
            sale=venda,
            user=request.user,
            reason=motivo,
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(
            request,
            f"Venda de {resumo['cliente']} em {resumo['data']:%d/%m/%Y} apagada. "
            f"Os animais voltaram ao estoque e o valor saiu do saldo do cliente."
        )
    except (ValidationError, DomainException) as exc:
        messages.error(request, _texto_erro(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("Erro ao apagar venda %s: %s", pk, exc, exc_info=True)
        messages.error(request, f"Erro ao apagar a venda: {exc}")

    return redirect(request.POST.get('next') or reverse('vendas:list'))


# ══════════════════════════════════════════════════════════════════════════════
# PDF
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def venda_pdf_view(request):
    """Exporta a lista de vendas respeitando exatamente os filtros da tela."""
    filtros = _ler_filtros(request)
    queryset = _aplicar_filtros(_queryset_base(), filtros)

    totais = queryset.aggregate(
        valor=Sum('total_amount'),
        animais=Sum('total_quantity'),
        peso=Sum('total_weight'),
    )

    return render_pdf(
        'finance/pdf/venda_list_pdf.html',
        {
            'vendas': queryset[:2000],
            'total_count': queryset.count(),
            'totais': totais,
            'periodo_label': rotulo_periodo(filtros['periodo']),
            'resumo_filtros': _resumo_filtros(filtros),
            'user': request.user,
        },
        nome_arquivo='vendas',
    )


def _resumo_filtros(filtros):
    """Frase que aparece no cabeçalho do PDF dizendo o que foi filtrado."""
    partes = []
    if filtros['cliente_id']:
        cliente = Client.objects.filter(pk=filtros['cliente_id']).first()
        if cliente:
            partes.append(f"Cliente: {cliente.name}")
    if filtros['fazenda_id']:
        fazenda = Farm.objects.filter(pk=filtros['fazenda_id']).first()
        if fazenda:
            partes.append(f"Fazenda: {fazenda.name}")
    if filtros['categoria_id']:
        categoria = AnimalCategory.objects.filter(pk=filtros['categoria_id']).first()
        if categoria:
            partes.append(f"Tipo de animal: {categoria.name}")
    if filtros['situacao']:
        partes.append(f"Situação: {dict(SaleStatus.choices).get(filtros['situacao'])}")
    if filtros['sem_valor'] == '1':
        partes.append("Somente vendas sem valor")
    if filtros['busca']:
        partes.append(f"Busca: \"{filtros['busca']}\"")
    return ' · '.join(partes)


# ══════════════════════════════════════════════════════════════════════════════
# MENSAGENS
# ══════════════════════════════════════════════════════════════════════════════

def _mensagem_sucesso(venda, verbo):
    from finance.templatetags.finance_tags import moeda_rs

    lotes = venda.items.count()
    texto = (
        f"Venda {verbo}: {venda.total_quantity} animal(is) "
        f"em {lotes} lote(s) para {venda.client.name}"
    )
    if venda.has_price:
        texto += f" — {moeda_rs(venda.total_amount)}"
    else:
        texto += " — sem valor informado"
    return texto + "."


def _texto_erro(exc):
    """
    Extrai a mensagem legível de um erro de domínio.

    `ValidationError` do Django e `DomainException` do inventário guardam o
    texto em lugares diferentes — `InsufficientStockError`, por exemplo, não
    é um `ValidationError`, então tratar só um dos dois deixaria o usuário com
    um erro 500 no lugar da explicação.
    """
    if isinstance(exc, ValidationError):
        if hasattr(exc, 'message'):
            return exc.message
        if hasattr(exc, 'messages') and exc.messages:
            return ' '.join(exc.messages)
    if isinstance(exc, DomainException):
        return exc.message
    return str(exc)

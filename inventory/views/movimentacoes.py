"""
Inventory Movimentações Views.

Este módulo gerencia todas as movimentações de estoque:
- Listagem com filtros avançados e paginação
- Nascimento, Desmame, Compra, Ajuste de Saldo
- Manejo (transferência entre fazendas)
- Mudança de categoria
- Cancelamento/estorno de movimentações
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Sum
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from typing import Tuple, Optional
import logging

from inventory.forms import (
    NascimentoForm, DesmameForm, SaldoForm, CompraForm,
    ManejoForm, MudancaCategoriaForm,
)
from inventory.services import MovementService
from inventory.domain import OperationType
from inventory.models import AnimalMovement
from operations.services import TransferService
from farms.models import Farm

logger = logging.getLogger(__name__)

# Tipos que são ocorrências (têm listagem separada)
OCCURRENCE_TYPES = {
    OperationType.MORTE.value,
    OperationType.ABATE.value,
    OperationType.VENDA.value,
    OperationType.DOACAO.value,
}

# Labels para tipos de movimentação
OPERATION_TYPE_LABELS = {
    OperationType.NASCIMENTO.value: 'Nascimento',
    OperationType.COMPRA.value: 'Compra',
    OperationType.DESMAME_IN.value: 'Desmame (+)',
    OperationType.DESMAME_OUT.value: 'Desmame (-)',
    OperationType.SALDO.value: 'Ajuste de Saldo',
    OperationType.MANEJO_IN.value: 'Manejo (Entrada)',
    OperationType.MANEJO_OUT.value: 'Manejo (Saída)',
    OperationType.MUDANCA_CATEGORIA_IN.value: 'Mudança Categoria (+)',
    OperationType.MUDANCA_CATEGORIA_OUT.value: 'Mudança Categoria (-)',
}

# Operações compostas: ao cancelar o lado OUT, também cancela o IN (e vice-versa)
# A lógica está no MovementService via related_movement
COMPOSITE_OPERATIONS = {
    OperationType.MANEJO_IN.value,
    OperationType.MANEJO_OUT.value,
    OperationType.MUDANCA_CATEGORIA_IN.value,
    OperationType.MUDANCA_CATEGORIA_OUT.value,
    OperationType.DESMAME_IN.value,
    OperationType.DESMAME_OUT.value,
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_filters_context(request) -> dict:
    search = request.GET.get('q', '').strip()
    farm_id = request.GET.get('farm', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    mes_str = request.GET.get('mes', '').strip()
    ano_str = request.GET.get('ano', '').strip()

    return {
        'search': search,
        'farm_id': farm_id,
        'tipo': tipo,
        'mes': mes_str,
        'ano': ano_str,
        'has_filters': any([search, farm_id, tipo, mes_str, ano_str]),
    }


def _apply_movement_filters(queryset, filters: dict):
    if filters['farm_id']:
        queryset = queryset.filter(farm_stock_balance__farm_id=filters['farm_id'])

    if filters['tipo']:
        queryset = queryset.filter(operation_type=filters['tipo'])

    if filters['mes'] and filters['mes'].isdigit():
        queryset = queryset.filter(timestamp__month=int(filters['mes']))

    if filters['ano'] and filters['ano'].isdigit():
        queryset = queryset.filter(timestamp__year=int(filters['ano']))

    if filters['search']:
        queryset = queryset.filter(
            Q(farm_stock_balance__farm__name__icontains=filters['search']) |
            Q(farm_stock_balance__animal_category__name__icontains=filters['search']) |
            Q(created_by__username__icontains=filters['search']) |
            Q(metadata__observacao__icontains=filters['search'])
        )

    return queryset


# ══════════════════════════════════════════════════════════════════════════════
# LISTAGEM
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def movement_list_view(request):
    try:
        filters = _build_filters_context(request)

        queryset = (
            AnimalMovement.objects
            .exclude(operation_type__in=OCCURRENCE_TYPES)
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'created_by',
            )
            # ── OBRIGATÓRIO: carrega cancellation para exibir status no template
            .prefetch_related(
                'cancellation',
                'cancellation__cancelled_by',
            )
            .order_by('-timestamp', '-created_at')
        )

        queryset = _apply_movement_filters(queryset, filters)

        paginator = Paginator(queryset, 25)
        page_number = request.GET.get('page', 1)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        tipos_disponiveis = (
            AnimalMovement.objects
            .exclude(operation_type__in=OCCURRENCE_TYPES)
            .values_list('operation_type', flat=True)
            .distinct()
            .order_by('operation_type')
        )

        ano_atual = timezone.now().year
        anos = list(range(ano_atual, ano_atual - 6, -1))
        meses = [
            ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
            ('4', 'Abril'), ('5', 'Maio'), ('6', 'Junho'),
            ('7', 'Julho'), ('8', 'Agosto'), ('9', 'Setembro'),
            ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
        ]

        stats = None
        if not filters['has_filters']:
            stats = queryset.aggregate(
                total_movimentacoes=Count('id'),
                total_quantidade=Sum('quantity')
            )

        context = {
            'page_obj': page_obj,
            'paginator': paginator,
            'total_count': paginator.count,
            'search_term': filters['search'],
            'farm_filtro': filters['farm_id'],
            'tipo_filtro': filters['tipo'],
            'mes_filtro': filters['mes'],
            'ano_filtro': filters['ano'],
            'filtros_ativos': filters['has_filters'],
            'farms': Farm.objects.filter(is_active=True).order_by('name'),
            'tipos_disponiveis': tipos_disponiveis,
            'operation_labels': OPERATION_TYPE_LABELS,
            'anos': anos,
            'meses': meses,
            'stats': stats,
        }

        return render(request, 'inventory/movement_list.html', context)

    except Exception as e:
        logger.error(f"Erro na listagem de movimentações: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar movimentações. Por favor, tente novamente.')
        return render(request, 'inventory/movement_list.html', {
            'page_obj': None,
            'total_count': 0,
        })


# ══════════════════════════════════════════════════════════════════════════════
# NASCIMENTO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def nascimento_create_view(request):
    if request.method == 'POST':
        form = NascimentoForm(request.POST)

        if form.is_valid():
            try:
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])

                movement = MovementService.execute_entrada(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.NASCIMENTO,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                logger.info(
                    f"Nascimento registrado por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Categoria: {movement.farm_stock_balance.animal_category.name}, "
                    f"Quantidade: {movement.quantity}"
                )

                messages.success(
                    request,
                    f'Nascimento registrado com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(f"Erro ao registrar nascimento: {str(e)}", exc_info=True)
                messages.error(request, f'Erro ao registrar nascimento: {str(e)}')
    else:
        form = NascimentoForm()

    context = {
        'form': form,
        'form_title': 'Registrar Nascimento',
        'form_description': 'Registre o nascimento de novos animais',
        'submit_button_text': 'Registrar Nascimento',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# DESMAME
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def desmame_create_view(request):
    if request.method == 'POST':
        form = DesmameForm(request.POST)

        if form.is_valid():
            try:
                qty_males = form.cleaned_data.get('quantity_males', 0) or 0
                qty_females = form.cleaned_data.get('quantity_females', 0) or 0

                results = TransferService.execute_desmame(
                    farm_id=str(form.cleaned_data['farm'].id),
                    quantity_males=qty_males,
                    quantity_females=qty_females,
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata={'observacao': form.cleaned_data.get('observacao', '')},
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                partes = []
                if qty_males > 0:
                    partes.append(f'{qty_males} B. Macho para Bois - 2A.')
                if qty_females > 0:
                    partes.append(f'{qty_females} B. Femea para Nov. - 2A.')

                farm_name = form.cleaned_data['farm'].name

                logger.info(
                    f"Desmame executado por {request.user.username}. "
                    f"Fazenda: {farm_name}, "
                    f"Machos: {qty_males}, Femeas: {qty_females}"
                )

                messages.success(
                    request,
                    f'Desmame realizado com sucesso em {farm_name}! '
                    f'{" e ".join(partes)}.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(
                    f"Erro ao registrar desmame: {str(e)}. "
                    f"Usuario: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, f'Erro ao registrar desmame: {str(e)}')
    else:
        form = DesmameForm()

    context = {
        'form': form,
        'form_title': 'Registrar Desmame',
        'form_description': (
            'O desmame transfere automaticamente: '
            'B. Macho para Bois - 2A. e B. Femea para Nov. - 2A.'
        ),
        'submit_button_text': 'Registrar Desmame',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# AJUSTE DE SALDO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def saldo_create_view(request):
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

                logger.warning(
                    f"Ajuste de saldo realizado por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Categoria: {movement.farm_stock_balance.animal_category.name}, "
                    f"Quantidade: {movement.quantity}"
                )

                messages.success(
                    request,
                    f'Saldo ajustado com sucesso! '
                    f'{movement.quantity} unidades adicionadas.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(f"Erro ao ajustar saldo: {str(e)}", exc_info=True)
                messages.error(request, f'Erro ao ajustar saldo: {str(e)}')
    else:
        form = SaldoForm()

    context = {
        'form': form,
        'form_title': 'Ajustar Saldo de Estoque',
        'form_description': 'Ajuste manual de saldo para correção de inventário',
        'submit_button_text': 'Confirmar Ajuste',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
        'form_badge': 'Atenção',
        'form_badge_color': 'yellow',
        'show_additional_info': True,
        'additional_info_text': (
            'Este ajuste deve ser usado apenas para correções de inventário '
            'ou reconciliações autorizadas. Todas as alterações são auditadas.'
        ),
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# COMPRA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def compra_create_view(request):
    if request.method == 'POST':
        form = CompraForm(request.POST)

        if form.is_valid():
            try:
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                if form.cleaned_data.get('preco_unitario'):
                    metadata['preco_unitario'] = str(form.cleaned_data['preco_unitario'])
                if form.cleaned_data.get('fornecedor'):
                    metadata['fornecedor'] = form.cleaned_data['fornecedor']

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

                logger.info(
                    f"Compra registrada por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Quantidade: {movement.quantity}"
                )

                messages.success(
                    request,
                    f'Compra registrada com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} adquiridos.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(f"Erro ao registrar compra: {str(e)}", exc_info=True)
                messages.error(request, f'Erro ao registrar compra: {str(e)}')
    else:
        form = CompraForm()

    context = {
        'form': form,
        'form_title': 'Registrar Compra',
        'form_description': 'Registre a aquisição de novos animais',
        'submit_button_text': 'Registrar Compra',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# MANEJO (Transferência entre Fazendas)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def manejo_create_view(request):
    if request.method == 'POST':
        form = ManejoForm(request.POST)

        if form.is_valid():
            try:
                if form.cleaned_data['farm'] == form.cleaned_data['target_farm']:
                    messages.error(request, 'Fazenda de origem e destino não podem ser as mesmas!')
                    return render(request, 'shared/generic_form.html', {
                        'form': form,
                        'form_title': 'Registrar Manejo',
                    })

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

                logger.info(
                    f"Manejo executado por {request.user.username}. "
                    f"{saida.quantity} {saida.farm_stock_balance.animal_category.name} "
                    f"de {saida.farm_stock_balance.farm.name} "
                    f"para {entrada.farm_stock_balance.farm.name}"
                )

                messages.success(
                    request,
                    f'Manejo realizado com sucesso! '
                    f'{saida.quantity} {saida.farm_stock_balance.animal_category.name} '
                    f'transferidos de {saida.farm_stock_balance.farm.name} '
                    f'para {entrada.farm_stock_balance.farm.name}.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(f"Erro ao executar manejo: {str(e)}", exc_info=True)
                messages.error(request, f'Erro no manejo: {str(e)}')
    else:
        form = ManejoForm()

    context = {
        'form': form,
        'form_title': 'Registrar Manejo',
        'form_description': 'Transfira animais entre fazendas',
        'submit_button_text': 'Executar Manejo',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# MUDANÇA DE CATEGORIA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def mudanca_categoria_create_view(request):
    if request.method == 'POST':
        form = MudancaCategoriaForm(request.POST)

        if form.is_valid():
            try:
                if form.cleaned_data['animal_category'] == form.cleaned_data['target_category']:
                    messages.error(request, 'Categoria de origem e destino não podem ser as mesmas!')
                    return render(request, 'shared/generic_form.html', {
                        'form': form,
                        'form_title': 'Mudança de Categoria',
                    })

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

                logger.info(
                    f"Mudança de categoria executada por {request.user.username}. "
                    f"{saida.quantity} animais de {saida.farm_stock_balance.animal_category.name} "
                    f"para {entrada.farm_stock_balance.animal_category.name}"
                )

                messages.success(
                    request,
                    f'Mudança de categoria realizada com sucesso! '
                    f'{saida.quantity} animais mudaram de '
                    f'{saida.farm_stock_balance.animal_category.name} '
                    f'para {entrada.farm_stock_balance.animal_category.name}.'
                )

                return redirect('movimentacoes:list')

            except Exception as e:
                logger.error(f"Erro ao executar mudança de categoria: {str(e)}", exc_info=True)
                messages.error(request, f'Erro na mudança de categoria: {str(e)}')
    else:
        form = MudancaCategoriaForm()

    context = {
        'form': form,
        'form_title': 'Mudança de Categoria',
        'form_description': 'Mude animais de uma categoria para outra',
        'submit_button_text': 'Executar Mudança',
        'cancel_url': reverse('movimentacoes:list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# CANCELAMENTO DE MOVIMENTAÇÃO (ESTORNO)
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def movement_cancel_view(request, pk):
    """
    Cancela (estorna) uma movimentação, revertendo seu efeito no saldo.

    - Apenas POST: protege contra cancelamentos via GET (bots/crawlers)
    - CSRF verificado automaticamente pelo Django middleware
    - Lógica delegada ao MovementService.cancel_movement()
    - Resposta dual: HTML parcial para HTMX, redirect para requests normais
    - Operações compostas (Manejo, Mudança Categoria, Desmame) cancelam
      os dois lados atomicamente
    """
    from inventory.models import AnimalMovementCancellation
    from inventory.domain import InsufficientStockError

    movement = get_object_or_404(
        AnimalMovement.objects
        .select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
        )
        .prefetch_related(
            'cancellation',
            'cancellation__cancelled_by',
        ),
        pk=pk,
    )

    is_htmx = request.headers.get('HX-Request') == 'true'

    # Verificação rápida: já cancelada?
    try:
        c = movement.cancellation
        error_msg = (
            f"Esta movimentação já foi cancelada em "
            f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
            f"por {c.cancelled_by.username}."
        )
        if is_htmx:
            return HttpResponse(
                _render_already_cancelled_row(movement, c),
                status=200,
            )
        messages.warning(request, error_msg)
        return redirect('movimentacoes:list')
    except AnimalMovementCancellation.DoesNotExist:
        pass

    try:
        result = MovementService.cancel_movement(
            movement_id=str(pk),
            cancelled_by=request.user,
            notes=request.POST.get('notes', ''),
        )

        logger.info(
            f"Cancelamento de movimentação por {request.user.username}. "
            f"Movement: {pk} | {result['operation_display']} | "
            f"Saldo: {result['balance_before']} → {result['balance_after']}"
        )

        if is_htmx:
            return HttpResponse(_render_cancelled_row(result), status=200)

        composite_msg = ' (operação composta — ambos os lados cancelados)' if result.get('is_composite') else ''
        messages.success(
            request,
            f"Movimentação estornada com sucesso.{composite_msg} "
            f"Saldo de {result['category']} em {result['farm']} revertido."
        )

    except (ValidationError, InsufficientStockError) as e:
        # Erros de negócio esperados — exibir mensagem clara ao usuário,
        # sem logar como ERROR (não é um bug, é uma regra de negócio)
        if isinstance(e, InsufficientStockError):
            farm = movement.farm_stock_balance.farm.name
            category = movement.farm_stock_balance.animal_category.name
            qty = movement.quantity
            current = movement.farm_stock_balance.current_quantity
            error_msg = (
                f"Não é possível estornar esta entrada de {qty} {category} em {farm}: "
                f"o saldo atual é {current} animal(is), inferior à quantidade que seria removida. "
                f"Provavelmente outros animais já saíram do estoque após esta entrada."
            )
        else:
            error_msg = e.message if hasattr(e, 'message') else str(e)

        logger.warning(
            f"Cancelamento bloqueado por regra de negócio. "
            f"Usuário: {request.user.username} | Movement: {pk} | Motivo: {error_msg}"
        )

        if is_htmx:
            return HttpResponse(
                f'<tr id="movement-row-{pk}"><td colspan="7" class="px-6 py-4 text-center">'
                f'<div class="inline-flex items-center gap-2 text-sm text-red-700 bg-red-50 '
                f'border border-red-200 rounded-xl px-4 py-3 max-w-lg">'
                f'<svg class="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
                f'<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" '
                f'd="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4'
                f'c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>'
                f'</svg>'
                f'<span>{error_msg}</span>'
                f'</div></td></tr>',
                status=200,
            )
        messages.error(request, error_msg)

    except Exception as e:
        logger.error(
            f"Erro inesperado no cancelamento de movimentação. "
            f"Usuário: {request.user.username} | Movement: {pk}",
            exc_info=True,
        )
        if is_htmx:
            return HttpResponse(
                f'<tr id="movement-row-{pk}"><td colspan="7" class="px-6 py-4 text-center">'
                '<span class="text-red-600 text-xs font-medium px-3 py-2 '
                'bg-red-50 rounded-lg inline-block">'
                'Erro interno. Tente novamente.</span></td></tr>',
                status=200,
            )
        messages.error(request, "Erro interno ao cancelar. Tente novamente.")

    return redirect('movimentacoes:list')


# ── Helpers de renderização HTML para respostas HTMX ─────────────────────────

def _render_cancelled_row(result: dict) -> str:
    """<tr> de confirmação após cancelamento bem-sucedido."""
    qty = result['quantity_restored']
    category = result['category']
    farm = result['farm']
    op = result['operation_display']
    composite = ' (operação composta)' if result.get('is_composite') else ''

    return f"""<tr class="bg-amber-50 transition-all duration-500">
        <td colspan="7" class="px-6 py-4">
            <div class="flex items-center justify-center gap-3 text-sm">
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                    <svg class="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="text-amber-800">
                    <span class="font-semibold">{op}</span> estornada{composite} —
                    saldo de <span class="font-semibold">{category}</span>
                    em <span class="font-semibold">{farm}</span> revertido
                    (<span class="font-semibold text-amber-700">{qty} animal(is)</span>)
                </div>
            </div>
        </td>
    </tr>"""


def _render_already_cancelled_row(movement, cancellation) -> str:
    """<tr> informando que a movimentação já foi cancelada (para HTMX)."""
    return f"""<tr class="bg-gray-50 opacity-60">
        <td colspan="7" class="px-6 py-4">
            <div class="flex items-center justify-center gap-2 text-sm text-gray-500">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
                Já cancelada em {cancellation.cancelled_at.strftime('%d/%m/%Y às %H:%M')}
                por {cancellation.cancelled_by.username}
            </div>
        </td>
    </tr>"""
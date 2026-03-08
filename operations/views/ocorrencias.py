"""
Operations Ocorrências Views - Morte, Abate, Venda, Doação.
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
import logging

from operations.forms import MorteForm, AbateForm, VendaForm, DoacaoForm
from operations.services.occurrence_service import OccurrenceService
from inventory.services import MovementService
from inventory.domain import OperationType
from inventory.models import AnimalMovement
from farms.models import Farm
from core.utils.decimal_utils import normalize_pt_br_decimal 

logger = logging.getLogger(__name__)

OCCURRENCE_TYPES = [
    OperationType.MORTE.value,
    OperationType.ABATE.value,
    OperationType.VENDA.value,
    OperationType.DOACAO.value,
]

OCCURRENCE_LABELS = {
    OperationType.MORTE.value: 'Morte',
    OperationType.ABATE.value: 'Abate',
    OperationType.VENDA.value: 'Venda',
    OperationType.DOACAO.value: 'Doação',
}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _build_filters_context(request) -> dict:
    search = request.GET.get('q', '').strip()
    tipo = request.GET.get('tipo', '').strip()
    farm_id = request.GET.get('farm', '').strip()
    mes_str = request.GET.get('mes', '').strip()
    ano_str = request.GET.get('ano', '').strip()

    return {
        'search': search,
        'tipo': tipo,
        'farm_id': farm_id,
        'mes': mes_str,
        'ano': ano_str,
        'has_filters': any([search, tipo, farm_id, mes_str, ano_str]),
    }


def _apply_occurrence_filters(queryset, filters: dict):
    if filters['tipo'] and filters['tipo'] in OCCURRENCE_TYPES:
        queryset = queryset.filter(operation_type=filters['tipo'])

    if filters['farm_id']:
        queryset = queryset.filter(farm_stock_balance__farm_id=filters['farm_id'])

    if filters['mes'] and filters['mes'].isdigit():
        queryset = queryset.filter(timestamp__month=int(filters['mes']))

    if filters['ano'] and filters['ano'].isdigit():
        queryset = queryset.filter(timestamp__year=int(filters['ano']))

    if filters['search']:
        queryset = queryset.filter(
            Q(farm_stock_balance__farm__name__icontains=filters['search']) |
            Q(farm_stock_balance__animal_category__name__icontains=filters['search']) |
            Q(client__name__icontains=filters['search']) |
            Q(death_reason__name__icontains=filters['search']) |
            Q(metadata__observacao__icontains=filters['search'])
        )

    return queryset


# ══════════════════════════════════════════════════════════════════════════════
# LISTAGEM
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def occurrence_list_view(request):
    try:
        filters = _build_filters_context(request)

        # ── CORREÇÃO: prefetch_related('cancellation') é obrigatório para que
        # movement.cancellation_id funcione no template e a linha apareça
        # como cancelada. Sem isso, o ORM não carrega o relacionamento OneToOne
        # e cancellation_id é sempre None.
        queryset = (
            AnimalMovement.objects
            .filter(operation_type__in=OCCURRENCE_TYPES)
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'client',
                'death_reason',
                'created_by',
            )
            .prefetch_related(
                'cancellation',
                'cancellation__cancelled_by',
            )
            .order_by('-timestamp', '-created_at')
        )

        queryset = _apply_occurrence_filters(queryset, filters)

        paginator = Paginator(queryset, 20)
        page_number = request.GET.get('page', 1)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        ano_atual = timezone.now().year
        anos = list(range(ano_atual, ano_atual - 6, -1))
        meses = [
            ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
            ('4', 'Abril'), ('5', 'Maio'), ('6', 'Junho'),
            ('7', 'Julho'), ('8', 'Agosto'), ('9', 'Setembro'),
            ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
        ]

        tipos_select = [(tipo, OCCURRENCE_LABELS[tipo]) for tipo in OCCURRENCE_TYPES]

        stats = None
        if not filters['has_filters']:
            stats = queryset.aggregate(
                total_ocorrencias=Count('id'),
                total_quantidade=Sum('quantity')
            )

        context = {
            'page_obj': page_obj,
            'paginator': paginator,
            'total_count': paginator.count,
            'search_term': filters['search'],
            'tipo_filtro': filters['tipo'],
            'farm_filtro': filters['farm_id'],
            'mes_filtro': filters['mes'],
            'ano_filtro': filters['ano'],
            'filtros_ativos': filters['has_filters'],
            'farms': Farm.objects.filter(is_active=True).order_by('name'),
            'tipos': tipos_select,
            'occurrence_labels': OCCURRENCE_LABELS,
            'anos': anos,
            'meses': meses,
            'stats': stats,
        }

        logger.info(
            f"Listagem de ocorrências acessada por {request.user.username}. "
            f"Total: {paginator.count}, Filtros: {filters['has_filters']}"
        )

        return render(request, 'operations/occurrence_list.html', context)

    except Exception as e:
        logger.error(f"Erro na listagem de ocorrências: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar ocorrências. Por favor, tente novamente.')
        return render(request, 'operations/occurrence_list.html', {
            'page_obj': None,
            'total_count': 0,
        })


# ══════════════════════════════════════════════════════════════════════════════
# MORTE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def morte_create_view(request):
    if request.method == 'POST':
        form = MorteForm(request.POST)

        if form.is_valid():
            try:
                metadata = {'observacao': form.cleaned_data.get('observacao', '')}
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])

                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.MORTE,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    death_reason_id=str(form.cleaned_data['death_reason'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                logger.warning(
                    f"Morte registrada por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Quantidade: {movement.quantity}, Motivo: {movement.death_reason.name}"
                )

                messages.success(
                    request,
                    f'Morte registrada com sucesso. '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'em {movement.farm_stock_balance.farm.name}. '
                    f'Motivo: {movement.death_reason.name}.'
                )
                return redirect('ocorrencias:list')

            except Exception as e:
                logger.error(f"Erro ao registrar morte: {str(e)}. Usuário: {request.user.username}", exc_info=True)
                messages.error(request, f'Erro ao registrar morte: {str(e)}')
        else:
            logger.warning(f"Validação falhou ao registrar morte. Usuário: {request.user.username}, Erros: {form.errors}")
    else:
        form = MorteForm()

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': 'Registrar Morte',
        'form_description': 'Registre a morte de animais',
        'submit_button_text': 'Registrar Morte',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'red',
    })


# ══════════════════════════════════════════════════════════════════════════════
# ABATE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def abate_create_view(request):
    if request.method == 'POST':
        form = AbateForm(request.POST)

        if form.is_valid():
            try:
                metadata = {'observacao': form.cleaned_data.get('observacao', '')}
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])

                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.ABATE,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                logger.info(f"Abate registrado por {request.user.username}. Quantidade: {movement.quantity}")
                messages.success(
                    request,
                    f'Abate registrado com sucesso. '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )
                return redirect('ocorrencias:list')

            except Exception as e:
                logger.error(f"Erro ao registrar abate: {str(e)}. Usuário: {request.user.username}", exc_info=True)
                messages.error(request, f'Erro ao registrar abate: {str(e)}')
        else:
            logger.warning(f"Validação falhou ao registrar abate. Usuário: {request.user.username}")
    else:
        form = AbateForm()

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': 'Registrar Abate',
        'form_description': 'Registre o abate de animais',
        'submit_button_text': 'Registrar Abate',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'orange',
    })


# ══════════════════════════════════════════════════════════════════════════════
# VENDA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def venda_create_view(request):
    if request.method == 'POST':
        form = VendaForm(request.POST)

        if form.is_valid():
            try:
                metadata = {'observacao': form.cleaned_data.get('observacao', '')}
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                if form.cleaned_data.get('preco_total'):
                    metadata['preco_total'] = str(form.cleaned_data['preco_total'])

                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.VENDA,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    client_id=str(form.cleaned_data['client'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                logger.info(
                    f"Venda registrada por {request.user.username}. "
                    f"Cliente: {movement.client.name}, Quantidade: {movement.quantity}"
                )
                messages.success(
                    request,
                    f'Venda registrada com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'vendidos para {movement.client.name}.'
                )
                return redirect('ocorrencias:list')

            except Exception as e:
                logger.error(f"Erro ao registrar venda: {str(e)}. Usuário: {request.user.username}", exc_info=True)
                messages.error(request, f'Erro ao registrar venda: {str(e)}')
        else:
            logger.warning(f"Validação falhou ao registrar venda. Usuário: {request.user.username}")
    else:
        form = VendaForm()

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': 'Registrar Venda',
        'form_description': 'Registre a venda de animais',
        'submit_button_text': 'Registrar Venda',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'green',
    })


# ══════════════════════════════════════════════════════════════════════════════
# DOAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def doacao_create_view(request):
    if request.method == 'POST':
        form = DoacaoForm(request.POST)

        if form.is_valid():
            try:
                metadata = {'observacao': form.cleaned_data.get('observacao', '')}
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])

                movement = MovementService.execute_saida(
                    farm_id=str(form.cleaned_data['farm'].id),
                    animal_category_id=str(form.cleaned_data['animal_category'].id),
                    operation_type=OperationType.DOACAO,
                    quantity=form.cleaned_data['quantity'],
                    user=request.user,
                    client_id=str(form.cleaned_data['client'].id),
                    timestamp=form.cleaned_data.get('timestamp'),
                    metadata=metadata,
                    ip_address=request.META.get('REMOTE_ADDR'),
                )

                logger.info(
                    f"Doação registrada por {request.user.username}. "
                    f"Beneficiado: {movement.client.name}, Quantidade: {movement.quantity}"
                )
                messages.success(
                    request,
                    f'Doação registrada com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'doados para {movement.client.name}.'
                )
                return redirect('ocorrencias:list')

            except Exception as e:
                logger.error(f"Erro ao registrar doação: {str(e)}. Usuário: {request.user.username}", exc_info=True)
                messages.error(request, f'Erro ao registrar doação: {str(e)}')
        else:
            logger.warning(f"Validação falhou ao registrar doação. Usuário: {request.user.username}")
    else:
        form = DoacaoForm()

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': 'Registrar Doação',
        'form_description': 'Registre a doação de animais',
        'submit_button_text': 'Registrar Doação',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'blue',
    })


# ══════════════════════════════════════════════════════════════════════════════
# CANCELAMENTO DE OCORRÊNCIA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["POST"])
def occurrence_cancel_view(request, pk):
    """
    Cancela (estorna) uma ocorrência, devolvendo o saldo ao estoque.

    - Apenas POST: protege contra cancelamentos via GET (bots/crawlers)
    - CSRF verificado automaticamente pelo Django middleware
    - Lógica delegada ao OccurrenceService
    - Resposta dual: HTML parcial para HTMX, redirect para requests normais
    """
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

    # Verificação rápida antes de chamar o service
    # Usamos try/except para evitar RelatedObjectDoesNotExist
    try:
        c = movement.cancellation
        error_msg = (
            f"Esta ocorrência já foi cancelada em "
            f"{c.cancelled_at.strftime('%d/%m/%Y às %H:%M')} "
            f"por {c.cancelled_by.username}."
        )
        if is_htmx:
            return HttpResponse(_render_already_cancelled_row(movement, c), status=200)
        messages.warning(request, error_msg)
        return redirect('ocorrencias:list')
    except Exception:
        pass  # ainda não cancelada — prosseguir

    try:
        result = OccurrenceService.cancel_occurrence(
            movement_id=str(pk),
            cancelled_by=request.user,
            notes=request.POST.get('notes', ''),
        )

        logger.info(
            f"Cancelamento realizado por {request.user.username}. "
            f"Movement: {pk} | {result['operation_display']} | "
            f"Saldo: {result['balance_before']} → {result['balance_after']}"
        )

        if is_htmx:
            return HttpResponse(_render_cancelled_row(result), status=200)

        messages.success(
            request,
            f"Ocorrência estornada com sucesso. "
            f"{result['quantity_restored']} animal(is) devolvido(s) "
            f"ao estoque de {result['category']} em {result['farm']}."
        )

    except ValidationError as e:
        error_msg = e.message if hasattr(e, 'message') else str(e)
        logger.warning(
            f"Tentativa de cancelamento inválida. "
            f"Usuário: {request.user.username} | Movement: {pk} | Erro: {error_msg}"
        )
        if is_htmx:
            return HttpResponse(
                f'<tr><td colspan="8" class="px-6 py-4 text-center">'
                f'<span class="text-red-600 text-xs font-medium px-3 py-2 '
                f'bg-red-50 rounded-lg inline-block">{error_msg}</span></td></tr>',
                status=200,
            )
        messages.error(request, error_msg)

    except Exception as e:
        logger.error(
            f"Erro inesperado no cancelamento. "
            f"Usuário: {request.user.username} | Movement: {pk}",
            exc_info=True
        )
        if is_htmx:
            return HttpResponse(
                '<tr><td colspan="8" class="px-6 py-4 text-center">'
                '<span class="text-red-600 text-xs font-medium px-3 py-2 '
                'bg-red-50 rounded-lg inline-block">'
                'Erro interno. Tente novamente.</span></td></tr>',
                status=200,
            )
        messages.error(request, "Erro interno ao cancelar. Tente novamente.")

    return redirect('ocorrencias:list')


# ── Helpers de renderização HTML para respostas HTMX ─────────────────────────

def _render_cancelled_row(result: dict) -> str:
    """<tr> de confirmação após cancelamento bem-sucedido."""
    qty = result['quantity_restored']
    category = result['category']
    farm = result['farm']
    op = result['operation_display']

    return f"""<tr class="bg-amber-50 transition-all duration-500">
        <td colspan="8" class="px-6 py-4">
            <div class="flex items-center justify-center gap-3 text-sm">
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                    <svg class="w-4 h-4 text-amber-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                              d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <div class="text-amber-800">
                    <span class="font-semibold">{op}</span> cancelada —
                    <span class="font-semibold text-green-700">+{qty}</span> animal(is)
                    devolvido(s) ao estoque de
                    <span class="font-semibold">{category}</span>
                    em <span class="font-semibold">{farm}</span>
                </div>
            </div>
        </td>
    </tr>"""


def _render_already_cancelled_row(movement, cancellation) -> str:
    """<tr> informando que a ocorrência já foi cancelada (para HTMX)."""
    return f"""<tr class="bg-gray-50 opacity-60">
        <td colspan="8" class="px-6 py-4">
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



@login_required
@require_http_methods(["GET", "POST"])
def occurrence_edit_view(request, pk):
    """
    Edita uma ocorrência ativa.
    GET  → form pré-preenchido
    POST → processa edição via OccurrenceService.edit_occurrence
    """
    from operations.models import Client, DeathReason

    movement = get_object_or_404(
        AnimalMovement.objects
        .select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'client',
            'death_reason',
            'created_by',
        )
        .prefetch_related('cancellation'),
        pk=pk,
        operation_type__in=OCCURRENCE_TYPES,
    )

    # Bloquear edição de canceladas — sem try/except: acessamos o manager direto
    from inventory.models import AnimalMovementCancellation
    if AnimalMovementCancellation.objects.filter(movement_id=pk).exists():
        messages.warning(request, "Ocorrências canceladas não podem ser editadas.")
        return redirect('ocorrencias:list')

    op = movement.operation_type
    meta = movement.metadata or {}

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', movement.quantity))
            observacao = request.POST.get('observacao', '').strip()
            timestamp_str = request.POST.get('timestamp', '').strip()
            client_id = request.POST.get('client_id', '').strip() or None
            death_reason_id = request.POST.get('death_reason_id', '').strip() or None

            # ── Normalização de decimais pt-BR ─────────────────────────────
            # O template envia "1.250,80" (string pt-BR com máscara).
            # normalize_pt_br_decimal() converte para Decimal antes de salvar.
            # Guardamos como str() no metadata para manter compatibilidade
            # com o restante do sistema (metadata é um JSONField de strings).

            peso_raw = request.POST.get('peso', '').strip()
            preco_raw = request.POST.get('preco_total', '').strip()

            peso_normalizado = None
            if peso_raw:
                try:
                    peso_normalizado = str(normalize_pt_br_decimal(peso_raw))
                except Exception:
                    messages.error(request, f'Peso inválido: "{peso_raw}". Use o formato 1.250,80.')
                    # Não retorna — deixa o form recarregar com os outros dados

            preco_normalizado = None
            if preco_raw:
                try:
                    preco_normalizado = str(normalize_pt_br_decimal(preco_raw))
                except Exception:
                    messages.error(request, f'Preço inválido: "{preco_raw}". Use o formato 15.000,00.')

            # Monta metadata apenas com campos preenchidos
            new_meta = {}
            if observacao:
                new_meta['observacao'] = observacao
            if peso_normalizado:
                new_meta['peso'] = peso_normalizado
            if preco_normalizado:
                new_meta['preco_total'] = preco_normalizado

            data = {
                'quantity': quantity,
                'metadata': new_meta,
            }

            if timestamp_str:
                from django.utils.dateparse import parse_datetime
                ts = parse_datetime(timestamp_str)
                if ts:
                    from django.utils import timezone as tz
                    if tz.is_naive(ts):
                        ts = tz.make_aware(ts)
                    data['timestamp'] = ts

            if client_id:
                data['client_id'] = client_id
            if death_reason_id:
                data['death_reason_id'] = death_reason_id

            result = OccurrenceService.edit_occurrence(
                movement_id=str(pk),
                updated_by=request.user,
                data=data,
            )

            messages.success(
                request,
                f"Ocorrência atualizada. "
                f"Quantidade: {result['quantity_before']} → {result['quantity_after']}."
                if result['quantity_before'] != result['quantity_after']
                else "Ocorrência atualizada com sucesso."
            )
            return redirect('ocorrencias:list')

        except ValidationError as e:
            error = e.message if hasattr(e, 'message') else str(e)
            messages.error(request, error)
        except (ValueError, TypeError) as e:
            messages.error(request, f"Dado inválido: {e}")
        except Exception as e:
            logger.error(f"Erro ao editar ocorrência {pk}: {e}", exc_info=True)
            messages.error(request, "Erro interno ao editar. Tente novamente.")

    # Contexto para o template
    clients = Client.objects.filter(is_active=True).order_by('name')
    death_reasons = DeathReason.objects.filter(is_active=True).order_by('name')

    context = {
        'movement': movement,
        'op': op,
        'meta': meta,
        'clients': clients,
        'death_reasons': death_reasons,
        'cancel_url': reverse('ocorrencias:list'),
        'timestamp_value': movement.timestamp.strftime('%Y-%m-%dT%H:%M'),
        'shows_client': op in ('VENDA', 'DOACAO'),
        'shows_death_reason': op == 'MORTE',
        'shows_preco': op == 'VENDA',
    }

    return render(request, 'operations/occurrence_edit.html', context)
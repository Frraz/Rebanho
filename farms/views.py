"""
Farms Views - Gerenciamento de Fazendas.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from typing import List, Dict, Any
import logging

from .models import Farm
from .forms import FarmForm
from inventory.models import FarmStockBalance
from inventory.services import StockQueryService

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_farm_summary_cached(farm_id: str, cache_timeout: int = 300) -> List[Dict]:
    """
    Obtém resumo de estoque da fazenda com cache.
    Usado apenas na listagem de fazendas (farm_list_view).
    NÃO usar em farm_detail_view — lá buscamos sempre do banco.
    """
    cache_key = f'farm_summary_{farm_id}'
    summary = cache.get(cache_key)

    if summary is None:
        try:
            summary = StockQueryService.get_farm_stock_summary(str(farm_id))
            cache.set(cache_key, summary, cache_timeout)
        except Exception as e:
            logger.error(f"Erro ao obter resumo da fazenda {farm_id}: {str(e)}")
            summary = []

    return summary


def _get_farm_summary_fresh(farm_id: str) -> List[Dict]:
    """
    Obtém resumo de estoque DIRETAMENTE do banco, sem cache.
    Usar em contextos onde o dado deve estar sempre atualizado
    (ex: farm_detail após cancelamento de ocorrência).
    """
    try:
        return StockQueryService.get_farm_stock_summary(str(farm_id))
    except Exception as e:
        logger.error(f"Erro ao obter resumo fresh da fazenda {farm_id}: {str(e)}")
        return []


def _calculate_total_animals(summary: List[Dict]) -> int:
    return sum(item.get('quantidade', 0) for item in summary)


def _invalidate_farm_cache(farm_id: str) -> None:
    cache_keys = [
        f'farm_summary_{farm_id}',
        f'farm_history_{farm_id}',
        'farms_list',
    ]
    cache.delete_many(cache_keys)


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_list_view(request):
    try:
        search_term = request.GET.get('q', '').strip()
        page_number = request.GET.get('page', 1)

        farms_queryset = Farm.objects.filter(is_active=True).select_related()

        if search_term:
            farms_queryset = farms_queryset.filter(
                Q(name__icontains=search_term) |
                Q(location__icontains=search_term)
            )

        farms_queryset = farms_queryset.order_by('name').annotate(
            total_animals=Sum('stock_balances__current_quantity'),
            categories_count=Count('stock_balances__animal_category', distinct=True)
        )

        paginator = Paginator(farms_queryset, 10)

        try:
            farms_page = paginator.page(page_number)
        except PageNotAnInteger:
            farms_page = paginator.page(1)
        except EmptyPage:
            farms_page = paginator.page(paginator.num_pages)

        farms_with_summary = []
        for farm in farms_page:
            total_animals = farm.total_animals or 0
            summary = _get_farm_summary_cached(str(farm.id)) if total_animals > 0 else []
            farms_with_summary.append({
                'farm': farm,
                'total_animals': total_animals,
                'categories_count': farm.categories_count or 0,
                'summary': summary,
            })

        context = {
            'farms_with_summary': farms_with_summary,
            'search_term': search_term,
            'total_count': paginator.count,
            'page_obj': farms_page,
            'is_paginated': paginator.num_pages > 1,
        }

        logger.info(
            f"Listagem de fazendas acessada por {request.user.username}. "
            f"Total: {paginator.count}, Busca: '{search_term}'"
        )

        return render(request, 'farms/farm_list.html', context)

    except Exception as e:
        logger.error(f"Erro na listagem de fazendas: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar a lista de fazendas. Por favor, tente novamente.')
        return render(request, 'farms/farm_list.html', {
            'farms_with_summary': [],
            'search_term': '',
            'total_count': 0,
        })


@login_required
@require_http_methods(["GET", "POST"])
def farm_create_view(request):
    if request.method == 'POST':
        form = FarmForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    farm = form.save(commit=False)
                    farm.save()

                    logger.info(f"Fazenda '{farm.name}' criada por {request.user.username}. ID: {farm.id}")
                    _invalidate_farm_cache(str(farm.id))

                    messages.success(
                        request,
                        f'Fazenda "{farm.name}" cadastrada com sucesso! '
                        f'Os saldos de estoque foram inicializados automaticamente.'
                    )
                    return redirect('farms:list')

            except Exception as e:
                logger.error(f"Erro ao criar fazenda: {str(e)}. Usuário: {request.user.username}", exc_info=True)
                messages.error(request, 'Erro ao cadastrar fazenda. Por favor, tente novamente.')
        else:
            logger.warning(f"Validação falhou ao criar fazenda. Usuário: {request.user.username}, Erros: {form.errors}")
    else:
        form = FarmForm()

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': 'Nova Fazenda',
        'form_description': 'Cadastre uma nova fazenda no sistema',
        'submit_button_text': 'Cadastrar Fazenda',
        'cancel_url': reverse('farms:list'),
        'show_back_button': True,
    })


@login_required
@require_http_methods(["GET", "POST"])
def farm_update_view(request, pk):
    farm = get_object_or_404(Farm, pk=pk)

    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)

        if form.is_valid():
            try:
                with transaction.atomic():
                    old_name = farm.name
                    farm = form.save()

                    logger.info(
                        f"Fazenda atualizada por {request.user.username}. "
                        f"ID: {farm.id}, '{old_name}' → '{farm.name}'"
                    )
                    _invalidate_farm_cache(str(farm.id))

                    messages.success(request, f'Fazenda "{farm.name}" atualizada com sucesso!')
                    return redirect('farms:list')

            except Exception as e:
                logger.error(f"Erro ao atualizar fazenda {farm.id}: {str(e)}.", exc_info=True)
                messages.error(request, 'Erro ao atualizar fazenda. Por favor, tente novamente.')
        else:
            logger.warning(f"Validação falhou ao atualizar fazenda {farm.id}. Erros: {form.errors}")
    else:
        form = FarmForm(instance=farm)

    return render(request, 'shared/generic_form.html', {
        'form': form,
        'form_title': f'Editar Fazenda: {farm.name}',
        'form_description': f'Atualize as informações da fazenda {farm.name}',
        'submit_button_text': 'Salvar Alterações',
        'cancel_url': reverse('farms:detail', args=[farm.pk]),
        'show_back_button': True,
        'form_badge': 'Editando',
        'form_badge_color': 'blue',
    })


@login_required
@require_http_methods(["GET"])
def farm_detail_view(request, pk):
    """
    Exibe detalhes completos de uma fazenda.

    IMPORTANTE: summary e total_animals são buscados DIRETAMENTE do banco
    (sem cache) para garantir que cancelamentos de ocorrências reflitam
    imediatamente, sem aguardar expiração do cache de 5 minutos.
    """
    try:
        farm = get_object_or_404(Farm, pk=pk)

        # ── Busca SEMPRE do banco — sem cache ──────────────────────────────
        # Motivo: cancelamentos de ocorrências atualizam o saldo via service
        # e invalidam o cache, mas se o Redis estiver lento ou a chave não
        # corresponder exatamente, o dado antigo seria exibido.
        # A query é simples e rápida; o custo do cache não compensa aqui.
        summary = _get_farm_summary_fresh(str(farm.id))
        total_animals = _calculate_total_animals(summary)

        # Histórico de movimentações (últimas 20)
        try:
            history = StockQueryService.get_movement_history(
                farm_id=str(farm.id),
                limit=20
            )
        except Exception as e:
            logger.error(f"Erro ao obter histórico da fazenda {farm.id}: {str(e)}")
            history = []

        # Estatísticas diretas do banco (sem cache — mesma razão)
        stock_stats = FarmStockBalance.objects.filter(farm=farm).aggregate(
            total_categories=Count('animal_category', distinct=True),
            total_quantity=Sum('current_quantity')
        )

        context = {
            'farm': farm,
            'summary': summary,
            'total_animals': total_animals,
            'history': history,
            'categories_count': stock_stats['total_categories'] or 0,
            'total_quantity': stock_stats['total_quantity'] or 0,
        }

        logger.info(
            f"Detalhes da fazenda '{farm.name}' (ID: {farm.id}) acessados por {request.user.username}"
        )

        return render(request, 'farms/farm_detail.html', context)

    except Exception as e:
        logger.error(f"Erro ao exibir detalhes da fazenda {pk}: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar detalhes da fazenda. Por favor, tente novamente.')
        return redirect('farms:list')


@login_required
@require_POST
def farm_deactivate_view(request, pk):
    farm = get_object_or_404(Farm, pk=pk)

    try:
        with transaction.atomic():
            farm_name = farm.name
            farm.deactivate()

            logger.warning(f"Fazenda '{farm_name}' (ID: {farm.id}) desativada por {request.user.username}")
            _invalidate_farm_cache(str(farm.id))

            messages.warning(
                request,
                f'Fazenda "{farm_name}" foi desativada. Você pode reativá-la a qualquer momento.'
            )

    except Exception as e:
        logger.error(f"Erro ao desativar fazenda {farm.id}: {str(e)}.", exc_info=True)
        messages.error(request, 'Erro ao desativar fazenda. Por favor, tente novamente.')

    return redirect('farms:list')


@login_required
@require_POST
def farm_activate_view(request, pk):
    farm = get_object_or_404(Farm, pk=pk)

    try:
        with transaction.atomic():
            farm_name = farm.name
            farm.activate()

            logger.info(f"Fazenda '{farm_name}' (ID: {farm.id}) reativada por {request.user.username}")
            _invalidate_farm_cache(str(farm.id))

            messages.success(request, f'Fazenda "{farm_name}" foi reativada com sucesso!')

    except Exception as e:
        logger.error(f"Erro ao reativar fazenda {farm.id}: {str(e)}.", exc_info=True)
        messages.error(request, 'Erro ao reativar fazenda. Por favor, tente novamente.')

    return redirect('farms:list')


@login_required
@require_http_methods(["GET"])
def farm_inactive_list_view(request):
    try:
        farms_queryset = Farm.objects.filter(is_active=False).order_by('-updated_at')

        paginator = Paginator(farms_queryset, 10)
        page_number = request.GET.get('page', 1)

        try:
            farms_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            farms_page = paginator.page(1)

        context = {
            'farms': farms_page,
            'total_count': paginator.count,
            'page_obj': farms_page,
            'is_paginated': paginator.num_pages > 1,
        }

        logger.info(
            f"Lista de fazendas inativas acessada por {request.user.username}. "
            f"Total: {paginator.count}"
        )

        return render(request, 'farms/farm_inactive_list.html', context)

    except Exception as e:
        logger.error(f"Erro ao listar fazendas inativas: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar fazendas inativas. Por favor, tente novamente.')
        return redirect('farms:list')
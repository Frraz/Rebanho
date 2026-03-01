"""
Inventory Cadastros Views - Tipos de Animal (Categorias).

Este módulo gerencia as categorias de animais do sistema:
- Listagem com busca e filtros
- Criação e edição de categorias
- Ativação/desativação (soft delete)
- Sincronização automática de saldos com fazendas

Regra de Negócio Importante:
Quando uma categoria é criada, saldos iniciais (zerados) são criados
automaticamente para todas as fazendas ativas via signal.
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
from typing import Optional
import logging

from inventory.models import AnimalCategory, FarmStockBalance
from inventory.forms import AnimalCategoryForm

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _invalidate_category_cache(category_id: Optional[str] = None) -> None:
    """Invalida cache relacionado a categorias."""
    cache_keys = ['categories_list']
    if category_id:
        cache_keys.append(f'category_stats_{category_id}')
    cache.delete_many(cache_keys)


def _get_category_stats(category_id: str) -> dict:
    """Obtém estatísticas de uma categoria com cache."""
    cache_key = f'category_stats_{category_id}'
    stats = cache.get(cache_key)

    if stats is None:
        try:
            stats = FarmStockBalance.objects.filter(
                animal_category_id=category_id,
                farm__is_active=True
            ).aggregate(
                total_animals=Sum('current_quantity'),
                farms_count=Count('farm', distinct=True)
            )
            stats['total_animals'] = stats['total_animals'] or 0
            stats['farms_count'] = stats['farms_count'] or 0
            cache.set(cache_key, stats, 300)  # 5 minutos
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas da categoria {category_id}: {str(e)}")
            stats = {'total_animals': 0, 'farms_count': 0}

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def animal_category_list_view(request):
    """
    Lista todas as categorias de animais ativas.

    Query Parameters:
        q (str): Termo de busca
        page (int): Número da página
    """
    try:
        search_term = request.GET.get('q', '').strip()
        page_number = request.GET.get('page', 1)

        categories_queryset = AnimalCategory.objects.filter(is_active=True)

        if search_term:
            categories_queryset = categories_queryset.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term)
            )

        categories_queryset = categories_queryset.order_by('name')

        # CORRIGIDO: related_name='stock_balances' (não 'farmstockbalance')
        categories_queryset = categories_queryset.annotate(
            total_animals=Sum('stock_balances__current_quantity'),
            farms_with_stock=Count('stock_balances__farm', distinct=True),
        )

        paginator = Paginator(categories_queryset, 15)

        try:
            categories_page = paginator.page(page_number)
        except PageNotAnInteger:
            categories_page = paginator.page(1)
        except EmptyPage:
            categories_page = paginator.page(paginator.num_pages)

        categories_with_stats = [
            {
                'category': category,
                'total_animals': category.total_animals or 0,
                'farms_count': category.farms_with_stock or 0,
            }
            for category in categories_page
        ]

        context = {
            'categories_with_stats': categories_with_stats,
            'search_term': search_term,
            'total_count': paginator.count,
            'page_obj': categories_page,
            'is_paginated': paginator.num_pages > 1,
        }

        logger.info(
            f"Listagem de categorias acessada por {request.user.username}. "
            f"Total: {paginator.count}, Busca: '{search_term}'"
        )

        return render(request, 'inventory/category_list.html', context)

    except Exception as e:
        logger.error(f"Erro na listagem de categorias: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar a lista de categorias. Por favor, tente novamente.')
        return render(request, 'inventory/category_list.html', {
            'categories_with_stats': [],
            'search_term': '',
            'total_count': 0,
        })


@login_required
@require_http_methods(["GET", "POST"])
def animal_category_create_view(request):
    """Cria uma nova categoria de animal."""
    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST)

        if form.is_valid():
            try:
                with transaction.atomic():
                    category = form.save()

                    from farms.models import Farm
                    farms_count = Farm.objects.filter(is_active=True).count()

                    logger.info(
                        f"Categoria '{category.name}' criada por {request.user.username}. "
                        f"ID: {category.id}. Saldos criados para {farms_count} fazendas."
                    )

                    _invalidate_category_cache(str(category.id))

                    messages.success(
                        request,
                        f'Categoria "{category.name}" cadastrada com sucesso! '
                        f'Saldos inicializados para {farms_count} fazenda{"s" if farms_count != 1 else ""}.'
                    )

                    return redirect('inventory_cadastros:category_list')

            except Exception as e:
                logger.error(
                    f"Erro ao criar categoria: {str(e)}. Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, 'Erro ao cadastrar categoria. Por favor, tente novamente.')
        else:
            logger.warning(
                f"Validação falhou ao criar categoria. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = AnimalCategoryForm()

    context = {
        'form': form,
        'form_title': 'Nova Categoria de Animal',
        'form_description': 'Cadastre um novo tipo de animal no sistema',
        'submit_button_text': 'Cadastrar Categoria',
        'cancel_url': reverse('inventory_cadastros:category_list'),
        'show_back_button': True,
    }

    return render(request, 'shared/generic_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def animal_category_update_view(request, pk):
    """Atualiza dados de uma categoria existente."""
    category = get_object_or_404(AnimalCategory, pk=pk)

    if request.method == 'POST':
        form = AnimalCategoryForm(request.POST, instance=category)

        if form.is_valid():
            try:
                with transaction.atomic():
                    old_name = category.name
                    category = form.save()

                    logger.info(
                        f"Categoria atualizada por {request.user.username}. "
                        f"ID: {category.id}, Nome antigo: '{old_name}', Nome novo: '{category.name}'"
                    )

                    _invalidate_category_cache(str(category.id))

                    messages.success(request, f'Categoria "{category.name}" atualizada com sucesso!')
                    return redirect('inventory_cadastros:category_list')

            except Exception as e:
                logger.error(
                    f"Erro ao atualizar categoria {category.id}: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, 'Erro ao atualizar categoria. Por favor, tente novamente.')
        else:
            logger.warning(
                f"Validação falhou ao atualizar categoria {category.id}. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = AnimalCategoryForm(instance=category)

    stats = _get_category_stats(str(category.id))

    context = {
        'form': form,
        'form_title': f'Editar Categoria: {category.name}',
        'form_description': f'Atualize as informações da categoria {category.name}',
        'submit_button_text': 'Salvar Alterações',
        'cancel_url': reverse('inventory_cadastros:category_list'),
        'show_back_button': True,
        'form_badge': 'Editando',
        'form_badge_color': 'blue',
        'show_additional_info': True,
        'additional_info_text': (
            f'Esta categoria possui {stats["total_animals"]} animais '
            f'distribuídos em {stats["farms_count"]} fazenda{"s" if stats["farms_count"] != 1 else ""}.'
        ),
    }

    return render(request, 'shared/generic_form.html', context)


@login_required
@require_POST
def animal_category_deactivate_view(request, pk):
    """
    Desativa uma categoria de animal (soft delete).
    Categorias com animais ativos não podem ser desativadas.
    """
    category = get_object_or_404(AnimalCategory, pk=pk)

    try:
        total_animals = FarmStockBalance.objects.filter(
            animal_category=category,
            farm__is_active=True
        ).aggregate(total=Sum('current_quantity'))['total'] or 0

        if total_animals > 0:
            logger.warning(
                f"Tentativa de desativar categoria '{category.name}' (ID: {category.id}) "
                f"com {total_animals} animais ativos. Usuário: {request.user.username}"
            )
            messages.error(
                request,
                f'Não é possível desativar a categoria "{category.name}" pois existem '
                f'{total_animals} animais ativos nesta categoria. '
                f'Transfira ou remova os animais primeiro.'
            )
            return redirect('inventory_cadastros:category_list')

        with transaction.atomic():
            category_name = category.name
            category.deactivate()

            logger.warning(
                f"Categoria '{category_name}' (ID: {category.id}) desativada por {request.user.username}"
            )
            _invalidate_category_cache(str(category.id))

            messages.warning(
                request,
                f'Categoria "{category_name}" foi desativada. Você pode reativá-la a qualquer momento.'
            )

    except Exception as e:
        logger.error(
            f"Erro ao desativar categoria {category.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(request, 'Erro ao desativar categoria. Por favor, tente novamente.')

    return redirect('inventory_cadastros:category_list')


@login_required
@require_POST
def animal_category_activate_view(request, pk):
    """Reativa uma categoria desativada."""
    category = get_object_or_404(AnimalCategory, pk=pk)

    try:
        with transaction.atomic():
            category_name = category.name
            category.activate()

            logger.info(
                f"Categoria '{category_name}' (ID: {category.id}) reativada por {request.user.username}"
            )
            _invalidate_category_cache(str(category.id))

            messages.success(request, f'Categoria "{category_name}" foi reativada com sucesso!')

    except Exception as e:
        logger.error(
            f"Erro ao reativar categoria {category.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(request, 'Erro ao reativar categoria. Por favor, tente novamente.')

    return redirect('inventory_cadastros:category_list')


@login_required
@require_http_methods(["GET"])
def animal_category_inactive_list_view(request):
    """Lista categorias inativas (desativadas)."""
    try:
        categories_queryset = AnimalCategory.objects.filter(
            is_active=False
        ).order_by('-created_at')

        paginator = Paginator(categories_queryset, 15)
        page_number = request.GET.get('page', 1)

        try:
            categories_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            categories_page = paginator.page(1)

        context = {
            'categories': categories_page,
            'total_count': paginator.count,
            'page_obj': categories_page,
            'is_paginated': paginator.num_pages > 1,
        }

        logger.info(
            f"Lista de categorias inativas acessada por {request.user.username}. "
            f"Total: {paginator.count}"
        )

        return render(request, 'inventory/category_inactive_list.html', context)

    except Exception as e:
        logger.error(f"Erro ao listar categorias inativas: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar categorias inativas. Por favor, tente novamente.')
        return redirect('inventory_cadastros:category_list')
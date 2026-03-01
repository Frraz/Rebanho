"""
Farms Views - Gerenciamento de Fazendas.

Este módulo gerencia todas as operações relacionadas a fazendas:
- Listagem com busca e filtros
- Criação e edição
- Detalhamento com resumo de estoque
- Ativação/desativação

Melhorias implementadas:
- Login obrigatório em todas as views
- Busca otimizada por nome
- Confirmação de ações destrutivas via POST
- Logging completo de operações
- Tratamento robusto de erros
- Cache de queries pesadas
- Mensagens profissionais sem emojis
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseRedirect
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
    
    Args:
        farm_id: ID da fazenda
        cache_timeout: Tempo de cache em segundos (padrão: 5 minutos)
        
    Returns:
        Lista de dicionários com resumo do estoque
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


def _calculate_total_animals(summary: List[Dict]) -> int:
    """
    Calcula total de animais a partir do resumo.
    
    Args:
        summary: Lista com resumo de estoque
        
    Returns:
        Total de animais
    """
    return sum(item.get('quantidade', 0) for item in summary)


def _invalidate_farm_cache(farm_id: str) -> None:
    """
    Invalida cache relacionado a uma fazenda.
    
    Args:
        farm_id: ID da fazenda
    """
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
    """
    Lista todas as fazendas ativas com resumo de estoque.
    
    Features:
    - Busca por nome (case-insensitive)
    - Paginação
    - Resumo de animais por fazenda
    - Cache de queries
    
    Query Parameters:
        q (str): Termo de busca
        page (int): Número da página
        
    Returns:
        Template renderizado com lista de fazendas
    """
    try:
        # Parâmetros de busca e paginação
        search_term = request.GET.get('q', '').strip()
        page_number = request.GET.get('page', 1)
        
        # Query base - fazendas ativas
        farms_queryset = Farm.objects.filter(is_active=True).select_related()
        
        # Aplicar busca se houver termo
        if search_term:
            farms_queryset = farms_queryset.filter(
                Q(name__icontains=search_term) |
                Q(location__icontains=search_term)
            )
        
        # Ordenação
        farms_queryset = farms_queryset.order_by('name')
        
        # Anotar com total de animais (otimização)
        farms_queryset = farms_queryset.annotate(
            total_animals=Sum('stock_balances__current_quantity'),
            categories_count=Count('stock_balances__animal_category', distinct=True)
        )
        
        # Paginação
        paginator = Paginator(farms_queryset, 10)  # 10 fazendas por página
        
        try:
            farms_page = paginator.page(page_number)
        except PageNotAnInteger:
            farms_page = paginator.page(1)
        except EmptyPage:
            farms_page = paginator.page(paginator.num_pages)
        
        # Processar dados para template
        farms_with_summary = []
        for farm in farms_page:
            # Usar valor anotado quando possível (mais rápido)
            total_animals = farm.total_animals or 0
            
            # Obter resumo detalhado apenas se necessário
            if total_animals > 0:
                summary = _get_farm_summary_cached(str(farm.id))
            else:
                summary = []
            
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
        messages.error(
            request,
            'Erro ao carregar a lista de fazendas. Por favor, tente novamente.'
        )
        return render(request, 'farms/farm_list.html', {
            'farms_with_summary': [],
            'search_term': '',
            'total_count': 0,
        })


@login_required
@require_http_methods(["GET", "POST"])
def farm_create_view(request):
    """
    Cria uma nova fazenda.
    
    Processo:
    1. Valida formulário
    2. Cria fazenda em transação atômica
    3. Inicializa saldos de estoque automaticamente (via signal)
    4. Invalida cache
    5. Redireciona para lista
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = FarmForm(request.POST)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Salvar fazenda
                    farm = form.save(commit=False)
                    farm.created_by = request.user  # Se houver campo de auditoria
                    farm.save()
                    
                    # Log de sucesso
                    logger.info(
                        f"Fazenda '{farm.name}' criada por {request.user.username}. "
                        f"ID: {farm.id}"
                    )
                    
                    # Invalidar cache
                    _invalidate_farm_cache(str(farm.id))
                    
                    # Mensagem de sucesso
                    messages.success(
                        request,
                        f'Fazenda "{farm.name}" cadastrada com sucesso! '
                        f'Os saldos de estoque foram inicializados automaticamente.'
                    )
                    
                    return redirect('farms:list')
                    
            except Exception as e:
                logger.error(
                    f"Erro ao criar fazenda: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao cadastrar fazenda. Por favor, tente novamente.'
                )
        else:
            # Log de validação falhou
            logger.warning(
                f"Validação de formulário falhou ao criar fazenda. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = FarmForm()
    
    context = {
        'form': form,
        'form_title': 'Nova Fazenda',
        'form_description': 'Cadastre uma nova fazenda no sistema',
        'submit_button_text': 'Cadastrar Fazenda',
        'cancel_url': reverse('farms:list'),
        'show_back_button': True,
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def farm_update_view(request, pk):
    """
    Atualiza dados de uma fazenda existente.
    
    Args:
        pk: Primary key da fazenda
        
    Returns:
        - GET: Formulário preenchido
        - POST: Redireciona para lista ou exibe erros
    """
    farm = get_object_or_404(Farm, pk=pk)
    
    if request.method == 'POST':
        form = FarmForm(request.POST, instance=farm)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Armazenar nome antigo para log
                    old_name = farm.name
                    
                    # Salvar alterações
                    farm = form.save(commit=False)
                    farm.updated_by = request.user  # Se houver campo de auditoria
                    farm.save()
                    
                    # Log de alteração
                    logger.info(
                        f"Fazenda atualizada por {request.user.username}. "
                        f"ID: {farm.id}, Nome antigo: '{old_name}', Nome novo: '{farm.name}'"
                    )
                    
                    # Invalidar cache
                    _invalidate_farm_cache(str(farm.id))
                    
                    # Mensagem de sucesso
                    messages.success(
                        request,
                        f'Fazenda "{farm.name}" atualizada com sucesso!'
                    )
                    
                    return redirect('farms:list')
                    
            except Exception as e:
                logger.error(
                    f"Erro ao atualizar fazenda {farm.id}: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao atualizar fazenda. Por favor, tente novamente.'
                )
        else:
            logger.warning(
                f"Validação falhou ao atualizar fazenda {farm.id}. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = FarmForm(instance=farm)
    
    context = {
        'form': farm,
        'form_title': f'Editar Fazenda: {farm.name}',
        'form_description': f'Atualize as informações da fazenda {farm.name}',
        'submit_button_text': 'Salvar Alterações',
        'cancel_url': reverse('farms:detail', args=[farm.pk]),
        'show_back_button': True,
        'form_badge': 'Editando',
        'form_badge_color': 'blue',
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_http_methods(["GET"])
def farm_detail_view(request, pk):
    """
    Exibe detalhes completos de uma fazenda.
    
    Informações exibidas:
    - Dados cadastrais
    - Resumo de estoque por categoria
    - Total de animais
    - Histórico de movimentações recentes
    
    Args:
        pk: Primary key da fazenda
        
    Returns:
        Template renderizado com detalhes da fazenda
    """
    try:
        farm = get_object_or_404(Farm, pk=pk)
        
        # Obter resumo de estoque (com cache)
        summary = _get_farm_summary_cached(str(farm.id))
        total_animals = _calculate_total_animals(summary)
        
        # Obter histórico de movimentações
        try:
            history = StockQueryService.get_movement_history(
                farm_id=str(farm.id),
                limit=20
            )
        except Exception as e:
            logger.error(f"Erro ao obter histórico da fazenda {farm.id}: {str(e)}")
            history = []
        
        # Estatísticas adicionais
        stock_stats = FarmStockBalance.objects.filter(
            farm=farm
        ).aggregate(
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
        logger.error(
            f"Erro ao exibir detalhes da fazenda {pk}: {str(e)}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao carregar detalhes da fazenda. Por favor, tente novamente.'
        )
        return redirect('farms:list')


@login_required
@require_POST
def farm_deactivate_view(request, pk):
    """
    Desativa uma fazenda.
    
    Apenas requisições POST são aceitas (confirmação via modal).
    A desativação é lógica (soft delete), mantendo dados históricos.
    
    Args:
        pk: Primary key da fazenda
        
    Returns:
        Redirect para lista de fazendas
    """
    farm = get_object_or_404(Farm, pk=pk)
    
    try:
        with transaction.atomic():
            farm_name = farm.name
            farm.deactivate()
            
            # Log de desativação
            logger.warning(
                f"Fazenda '{farm_name}' (ID: {farm.id}) desativada por {request.user.username}"
            )
            
            # Invalidar cache
            _invalidate_farm_cache(str(farm.id))
            
            # Mensagem ao usuário
            messages.warning(
                request,
                f'Fazenda "{farm_name}" foi desativada. '
                f'Você pode reativá-la a qualquer momento.'
            )
            
    except Exception as e:
        logger.error(
            f"Erro ao desativar fazenda {farm.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao desativar fazenda. Por favor, tente novamente.'
        )
    
    return redirect('farms:list')


@login_required
@require_POST
def farm_activate_view(request, pk):
    """
    Reativa uma fazenda desativada.
    
    Apenas requisições POST são aceitas.
    
    Args:
        pk: Primary key da fazenda
        
    Returns:
        Redirect para lista de fazendas
    """
    farm = get_object_or_404(Farm, pk=pk)
    
    try:
        with transaction.atomic():
            farm_name = farm.name
            farm.activate()
            
            # Log de reativação
            logger.info(
                f"Fazenda '{farm_name}' (ID: {farm.id}) reativada por {request.user.username}"
            )
            
            # Invalidar cache
            _invalidate_farm_cache(str(farm.id))
            
            # Mensagem ao usuário
            messages.success(
                request,
                f'Fazenda "{farm_name}" foi reativada com sucesso!'
            )
            
    except Exception as e:
        logger.error(
            f"Erro ao reativar fazenda {farm.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao reativar fazenda. Por favor, tente novamente.'
        )
    
    return redirect('farms:list')


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_inactive_list_view(request):
    """
    Lista fazendas inativas (desativadas).
    
    Permite ao administrador visualizar e reativar fazendas.
    
    Returns:
        Template renderizado com lista de fazendas inativas
    """
    try:
        farms_queryset = Farm.objects.filter(is_active=False).order_by('-updated_at')
        
        # Paginação
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
        messages.error(
            request,
            'Erro ao carregar fazendas inativas. Por favor, tente novamente.'
        )
        return redirect('farms:list')
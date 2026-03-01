"""
Operations Ocorrências Views - Morte, Abate, Venda, Doação.

Este módulo gerencia todas as ocorrências (saídas definitivas) do sistema:
- Listagem com filtros avançados e paginação
- Morte (com tipo de morte obrigatório)
- Abate (para consumo)
- Venda (com cliente e valor)
- Doação (com cliente)

Melhorias implementadas:
- Login obrigatório em todas as views
- Filtros: tipo, fazenda, período, busca livre
- Paginação otimizada
- Logging completo de operações
- Tratamento robusto de erros
- Mensagens profissionais sem emojis
- Validações de negócio
- Transações atômicas

Observações:
- Todas as ocorrências são SAÍDAS definitivas
- Modelo correto: AnimalMovement (não AnimalOccurrence)
- Filtros via farm_stock_balance__farm_id
- Morte requer death_reason obrigatório
- Venda e Doação requerem client obrigatório
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q, Count, Sum
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from typing import List, Dict, Optional
import logging

from operations.forms import MorteForm, AbateForm, VendaForm, DoacaoForm
from inventory.services import MovementService
from inventory.domain import OperationType
from inventory.models import AnimalMovement
from farms.models import Farm

logger = logging.getLogger(__name__)

# Tipos de operação classificados como "ocorrências" (sempre saídas)
OCCURRENCE_TYPES = [
    OperationType.MORTE.value,
    OperationType.ABATE.value,
    OperationType.VENDA.value,
    OperationType.DOACAO.value,
]

# Labels para tipos de ocorrência (sem emojis)
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
    """
    Extrai e valida filtros da requisição.
    
    Args:
        request: HttpRequest
        
    Returns:
        Dicionário com filtros validados
    """
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
    """
    Aplica filtros ao queryset de ocorrências.
    
    Args:
        queryset: QuerySet base
        filters: Dicionário de filtros
        
    Returns:
        QuerySet filtrado
    """
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
    """
    Lista de ocorrências com filtros avançados e paginação.
    
    Exibe apenas operações classificadas como ocorrências (saídas definitivas).
    
    Filtros disponíveis:
        q (str): Busca livre (fazenda, categoria, cliente, tipo de morte, observação)
        tipo (str): Tipo de ocorrência (MORTE, ABATE, VENDA, DOACAO)
        farm (uuid): Filtrar por fazenda
        mes (int): Filtrar por mês (1-12)
        ano (int): Filtrar por ano
        page (int): Número da página
        
    Returns:
        Template renderizado com lista paginada de ocorrências
    """
    try:
        # Extrair filtros
        filters = _build_filters_context(request)
        
        # Query base: apenas ocorrências
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
            .order_by('-timestamp', '-created_at')
        )
        
        # Aplicar filtros
        queryset = _apply_occurrence_filters(queryset, filters)
        
        # Paginação
        paginator = Paginator(queryset, 20)  # 20 por página
        page_number = request.GET.get('page', 1)
        
        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        
        # Dados para filtros
        ano_atual = timezone.now().year
        anos = list(range(ano_atual, ano_atual - 6, -1))
        meses = [
            ('1', 'Janeiro'), ('2', 'Fevereiro'), ('3', 'Março'),
            ('4', 'Abril'), ('5', 'Maio'), ('6', 'Junho'),
            ('7', 'Julho'), ('8', 'Agosto'), ('9', 'Setembro'),
            ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
        ]
        
        # Tipos para select (formato para template)
        tipos_select = [
            (tipo, OCCURRENCE_LABELS[tipo])
            for tipo in OCCURRENCE_TYPES
        ]
        
        # Estatísticas rápidas (se não houver filtros)
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
        messages.error(
            request,
            'Erro ao carregar ocorrências. Por favor, tente novamente.'
        )
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
    """
    Registra morte de animais.
    
    Campos obrigatórios:
    - farm: Fazenda onde ocorreu a morte
    - animal_category: Categoria do animal
    - quantity: Quantidade de animais
    - death_reason: Motivo da morte
    
    Campos opcionais:
    - peso: Peso médio dos animais
    - observacao: Observações adicionais
    - timestamp: Data/hora da morte (padrão: agora)
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = MorteForm(request.POST)
        
        if form.is_valid():
            try:
                # Preparar metadata
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                
                # Executar ocorrência
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
                
                # Log de sucesso
                logger.warning(
                    f"Morte registrada por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Categoria: {movement.farm_stock_balance.animal_category.name}, "
                    f"Quantidade: {movement.quantity}, "
                    f"Motivo: {movement.death_reason.name}"
                )
                
                # Mensagem de sucesso
                messages.success(
                    request,
                    f'Morte registrada com sucesso. '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'em {movement.farm_stock_balance.farm.name}. '
                    f'Motivo: {movement.death_reason.name}.'
                )
                
                return redirect('ocorrencias:list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao registrar morte: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    f'Erro ao registrar morte: {str(e)}'
                )
        else:
            logger.warning(
                f"Validação falhou ao registrar morte. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = MorteForm()
    
    context = {
        'form': form,
        'form_title': 'Registrar Morte',
        'form_description': 'Registre a morte de animais',
        'submit_button_text': 'Registrar Morte',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'red',
    }
    
    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# ABATE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def abate_create_view(request):
    """
    Registra abate de animais.
    
    Campos opcionais:
    - peso: Peso médio dos animais abatidos
    - observacao: Observações adicionais
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = AbateForm(request.POST)
        
        if form.is_valid():
            try:
                # Preparar metadata
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                
                # Executar ocorrência
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
                
                logger.info(
                    f"Abate registrado por {request.user.username}. "
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Quantidade: {movement.quantity}"
                )
                
                messages.success(
                    request,
                    f'Abate registrado com sucesso. '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'em {movement.farm_stock_balance.farm.name}.'
                )
                
                return redirect('ocorrencias:list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao registrar abate: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, f'Erro ao registrar abate: {str(e)}')
        else:
            logger.warning(
                f"Validação falhou ao registrar abate. "
                f"Usuário: {request.user.username}"
            )
    else:
        form = AbateForm()
    
    context = {
        'form': form,
        'form_title': 'Registrar Abate',
        'form_description': 'Registre o abate de animais',
        'submit_button_text': 'Registrar Abate',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'orange',
    }
    
    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# VENDA
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def venda_create_view(request):
    """
    Registra venda de animais.
    
    Campos obrigatórios:
    - client: Cliente comprador
    
    Campos opcionais:
    - peso: Peso total vendido
    - preco_total: Valor total da venda
    - observacao: Observações adicionais
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = VendaForm(request.POST)
        
        if form.is_valid():
            try:
                # Preparar metadata
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                
                if form.cleaned_data.get('preco_total'):
                    metadata['preco_total'] = str(form.cleaned_data['preco_total'])
                
                # Executar ocorrência
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
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Cliente: {movement.client.name}, "
                    f"Quantidade: {movement.quantity}, "
                    f"Valor: {metadata.get('preco_total', 'N/A')}"
                )
                
                messages.success(
                    request,
                    f'Venda registrada com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'vendidos para {movement.client.name}.'
                )
                
                return redirect('ocorrencias:list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao registrar venda: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, f'Erro ao registrar venda: {str(e)}')
        else:
            logger.warning(
                f"Validação falhou ao registrar venda. "
                f"Usuário: {request.user.username}"
            )
    else:
        form = VendaForm()
    
    context = {
        'form': form,
        'form_title': 'Registrar Venda',
        'form_description': 'Registre a venda de animais',
        'submit_button_text': 'Registrar Venda',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'green',
    }
    
    return render(request, 'shared/generic_form.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# DOAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET", "POST"])
def doacao_create_view(request):
    """
    Registra doação de animais.
    
    Campos obrigatórios:
    - client: Cliente/instituição beneficiada
    
    Campos opcionais:
    - peso: Peso total doado
    - observacao: Observações adicionais
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = DoacaoForm(request.POST)
        
        if form.is_valid():
            try:
                # Preparar metadata
                metadata = {
                    'observacao': form.cleaned_data.get('observacao', ''),
                }
                
                if form.cleaned_data.get('peso'):
                    metadata['peso'] = str(form.cleaned_data['peso'])
                
                # Executar ocorrência
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
                    f"Fazenda: {movement.farm_stock_balance.farm.name}, "
                    f"Beneficiado: {movement.client.name}, "
                    f"Quantidade: {movement.quantity}"
                )
                
                messages.success(
                    request,
                    f'Doação registrada com sucesso! '
                    f'{movement.quantity} {movement.farm_stock_balance.animal_category.name} '
                    f'doados para {movement.client.name}.'
                )
                
                return redirect('ocorrencias:list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao registrar doação: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(request, f'Erro ao registrar doação: {str(e)}')
        else:
            logger.warning(
                f"Validação falhou ao registrar doação. "
                f"Usuário: {request.user.username}"
            )
    else:
        form = DoacaoForm()
    
    context = {
        'form': form,
        'form_title': 'Registrar Doação',
        'form_description': 'Registre a doação de animais',
        'submit_button_text': 'Registrar Doação',
        'cancel_url': reverse('ocorrencias:list'),
        'show_back_button': True,
        'form_badge': 'Ocorrência',
        'form_badge_color': 'blue',
    }
    
    return render(request, 'shared/generic_form.html', context)
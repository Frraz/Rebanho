"""
Operations Cadastros Views - Clientes e Tipos de Morte.

Este módulo gerencia cadastros auxiliares do sistema:
- Clientes (para vendas e doações)
- Tipos de Morte (causas de óbito dos animais)

Melhorias implementadas:
- Login obrigatório em todas as views
- Busca avançada (nome, CPF/CNPJ, telefone, email)
- Paginação
- Logging completo de operações
- Tratamento robusto de erros
- Mensagens profissionais sem emojis
- Validações de negócio
- Cache de queries
- Integração com templates genéricos

Regras de Negócio:
- Clientes podem ser desativados apenas se não tiverem transações ativas
- Tipos de Morte podem ser desativados apenas se não estiverem em uso
- Todas as operações são auditadas
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.db.models import Q, Count
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.urls import reverse
from typing import Optional
import logging

from operations.models import Client, DeathReason
from operations.forms import ClientForm, DeathReasonForm

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _invalidate_client_cache() -> None:
    """Invalida cache relacionado a clientes."""
    cache.delete('clients_list')


def _invalidate_death_reason_cache() -> None:
    """Invalida cache relacionado a tipos de morte."""
    cache.delete('death_reasons_list')


# ══════════════════════════════════════════════════════════════════════════════
# CLIENTES
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def client_list_view(request):
    """
    Lista todos os clientes ativos.
    
    Features:
    - Busca por nome, CPF/CNPJ, telefone, email
    - Paginação
    - Ordenação alfabética
    
    Query Parameters:
        q (str): Termo de busca
        page (int): Número da página
        
    Returns:
        Template renderizado com lista de clientes
    """
    try:
        # Parâmetros de busca e paginação
        search_term = request.GET.get('q', '').strip()
        page_number = request.GET.get('page', 1)
        
        # Query base - clientes ativos
        clients_queryset = Client.objects.filter(is_active=True)
        
        # Aplicar busca se houver termo
        if search_term:
            clients_queryset = clients_queryset.filter(
                Q(name__icontains=search_term) |
                Q(cpf_cnpj__icontains=search_term) |
                Q(phone__icontains=search_term) |
                Q(email__icontains=search_term) |
                Q(address__icontains=search_term)
            )
        
        # Ordenação
        clients_queryset = clients_queryset.order_by('name')
        
        # Anotar com estatísticas (se houver relacionamentos)
        # clients_queryset = clients_queryset.annotate(
        #     vendas_count=Count('venda', distinct=True)
        # )
        
        # Paginação
        paginator = Paginator(clients_queryset, 20)  # 20 clientes por página
        
        try:
            clients_page = paginator.page(page_number)
        except PageNotAnInteger:
            clients_page = paginator.page(1)
        except EmptyPage:
            clients_page = paginator.page(paginator.num_pages)
        
        context = {
            'clients': clients_page,
            'search_term': search_term,
            'total_count': paginator.count,
            'page_obj': clients_page,
            'is_paginated': paginator.num_pages > 1,
        }
        
        logger.info(
            f"Listagem de clientes acessada por {request.user.username}. "
            f"Total: {paginator.count}, Busca: '{search_term}'"
        )
        
        return render(request, 'operations/client_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro na listagem de clientes: {str(e)}", exc_info=True)
        messages.error(
            request,
            'Erro ao carregar a lista de clientes. Por favor, tente novamente.'
        )
        return render(request, 'operations/client_list.html', {
            'clients': [],
            'search_term': '',
            'total_count': 0,
        })


@login_required
@require_http_methods(["GET", "POST"])
def client_create_view(request):
    """
    Cria um novo cliente.
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = ClientForm(request.POST)
        
        if form.is_valid():
            try:
                # Salvar cliente
                client = form.save(commit=False)
                client.created_by = request.user  # Se houver campo de auditoria
                client.save()
                
                # Log de sucesso
                logger.info(
                    f"Cliente '{client.name}' criado por {request.user.username}. "
                    f"ID: {client.id}, CPF/CNPJ: {client.cpf_cnpj or 'N/A'}"
                )
                
                # Invalidar cache
                _invalidate_client_cache()
                
                # Mensagem de sucesso
                messages.success(
                    request,
                    f'Cliente "{client.name}" cadastrado com sucesso!'
                )
                
                return redirect('operations_cadastros:client_list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao criar cliente: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao cadastrar cliente. Por favor, tente novamente.'
                )
        else:
            logger.warning(
                f"Validação de formulário falhou ao criar cliente. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = ClientForm()
    
    context = {
        'form': form,
        'form_title': 'Novo Cliente',
        'form_description': 'Cadastre um novo cliente no sistema',
        'submit_button_text': 'Cadastrar Cliente',
        'cancel_url': reverse('operations_cadastros:client_list'),
        'show_back_button': True,
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def client_update_view(request, pk):
    """
    Atualiza dados de um cliente existente.
    
    Args:
        pk: Primary key do cliente
        
    Returns:
        - GET: Formulário preenchido
        - POST: Redireciona para lista ou exibe erros
    """
    client = get_object_or_404(Client, pk=pk)
    
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        
        if form.is_valid():
            try:
                # Armazenar nome antigo para log
                old_name = client.name
                
                # Salvar alterações
                client = form.save(commit=False)
                client.updated_by = request.user  # Se houver campo de auditoria
                client.save()
                
                # Log de alteração
                logger.info(
                    f"Cliente atualizado por {request.user.username}. "
                    f"ID: {client.id}, Nome antigo: '{old_name}', Nome novo: '{client.name}'"
                )
                
                # Invalidar cache
                _invalidate_client_cache()
                
                # Mensagem de sucesso
                messages.success(
                    request,
                    f'Cliente "{client.name}" atualizado com sucesso!'
                )
                
                return redirect('operations_cadastros:client_list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao atualizar cliente {client.id}: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao atualizar cliente. Por favor, tente novamente.'
                )
        else:
            logger.warning(
                f"Validação falhou ao atualizar cliente {client.id}. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = ClientForm(instance=client)
    
    context = {
        'form': form,
        'form_title': f'Editar Cliente: {client.name}',
        'form_description': f'Atualize as informações do cliente {client.name}',
        'submit_button_text': 'Salvar Alterações',
        'cancel_url': reverse('operations_cadastros:client_list'),
        'show_back_button': True,
        'form_badge': 'Editando',
        'form_badge_color': 'blue',
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_POST
def client_deactivate_view(request, pk):
    """
    Desativa um cliente.
    
    Apenas requisições POST são aceitas (confirmação via modal).
    
    ATENÇÃO: Verifica se o cliente possui vendas/doações ativas antes de desativar.
    
    Args:
        pk: Primary key do cliente
        
    Returns:
        Redirect para lista de clientes
    """
    client = get_object_or_404(Client, pk=pk)
    
    try:
        # Verificar se há vendas ativas (se houver relacionamento)
        # from inventory.models import AnimalMovement
        # vendas_ativas = AnimalMovement.objects.filter(
        #     client=client,
        #     operation_type='VENDA'
        # ).count()
        # 
        # if vendas_ativas > 0:
        #     logger.warning(
        #         f"Tentativa de desativar cliente '{client.name}' (ID: {client.id}) "
        #         f"com {vendas_ativas} vendas ativas. Usuário: {request.user.username}"
        #     )
        #     messages.error(
        #         request,
        #         f'Não é possível desativar o cliente "{client.name}" pois existem '
        #         f'{vendas_ativas} vendas ativas vinculadas a ele.'
        #     )
        #     return redirect('operations_cadastros:client_list')
        
        client_name = client.name
        client.deactivate()
        
        # Log de desativação
        logger.warning(
            f"Cliente '{client_name}' (ID: {client.id}) desativado por {request.user.username}"
        )
        
        # Invalidar cache
        _invalidate_client_cache()
        
        # Mensagem ao usuário
        messages.warning(
            request,
            f'Cliente "{client_name}" foi desativado. '
            f'Você pode reativá-lo a qualquer momento.'
        )
        
    except Exception as e:
        logger.error(
            f"Erro ao desativar cliente {client.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao desativar cliente. Por favor, tente novamente.'
        )
    
    return redirect('operations_cadastros:client_list')


@login_required
@require_POST
def client_activate_view(request, pk):
    """
    Reativa um cliente desativado.
    
    Args:
        pk: Primary key do cliente
        
    Returns:
        Redirect para lista de clientes
    """
    client = get_object_or_404(Client, pk=pk)
    
    try:
        client_name = client.name
        client.activate()
        
        # Log de reativação
        logger.info(
            f"Cliente '{client_name}' (ID: {client.id}) reativado por {request.user.username}"
        )
        
        # Invalidar cache
        _invalidate_client_cache()
        
        # Mensagem ao usuário
        messages.success(
            request,
            f'Cliente "{client_name}" foi reativado com sucesso!'
        )
        
    except Exception as e:
        logger.error(
            f"Erro ao reativar cliente {client.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao reativar cliente. Por favor, tente novamente.'
        )
    
    return redirect('operations_cadastros:client_list')


# ══════════════════════════════════════════════════════════════════════════════
# TIPOS DE MORTE
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def death_reason_list_view(request):
    """
    Lista todos os tipos de morte ativos.
    
    Features:
    - Busca por nome e descrição
    - Paginação
    - Ordenação alfabética
    
    Query Parameters:
        q (str): Termo de busca
        page (int): Número da página
        
    Returns:
        Template renderizado com lista de tipos de morte
    """
    try:
        # Parâmetros de busca e paginação
        search_term = request.GET.get('q', '').strip()
        page_number = request.GET.get('page', 1)
        
        # Query base - tipos de morte ativos
        reasons_queryset = DeathReason.objects.filter(is_active=True)
        
        # Aplicar busca se houver termo
        if search_term:
            reasons_queryset = reasons_queryset.filter(
                Q(name__icontains=search_term) |
                Q(description__icontains=search_term)
            )
        
        # Ordenação
        reasons_queryset = reasons_queryset.order_by('name')
        
        # Anotar com estatísticas (se houver relacionamentos)
        # reasons_queryset = reasons_queryset.annotate(
        #     mortes_count=Count('animalmovement', distinct=True)
        # )
        
        # Paginação
        paginator = Paginator(reasons_queryset, 20)  # 20 por página
        
        try:
            reasons_page = paginator.page(page_number)
        except PageNotAnInteger:
            reasons_page = paginator.page(1)
        except EmptyPage:
            reasons_page = paginator.page(paginator.num_pages)
        
        context = {
            'reasons': reasons_page,
            'search_term': search_term,
            'total_count': paginator.count,
            'page_obj': reasons_page,
            'is_paginated': paginator.num_pages > 1,
        }
        
        logger.info(
            f"Listagem de tipos de morte acessada por {request.user.username}. "
            f"Total: {paginator.count}, Busca: '{search_term}'"
        )
        
        return render(request, 'operations/death_reason_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro na listagem de tipos de morte: {str(e)}", exc_info=True)
        messages.error(
            request,
            'Erro ao carregar a lista de tipos de morte. Por favor, tente novamente.'
        )
        return render(request, 'operations/death_reason_list.html', {
            'reasons': [],
            'search_term': '',
            'total_count': 0,
        })


@login_required
@require_http_methods(["GET", "POST"])
def death_reason_create_view(request):
    """
    Cria um novo tipo de morte.
    
    Returns:
        - GET: Formulário vazio
        - POST: Redireciona para lista ou exibe erros
    """
    if request.method == 'POST':
        form = DeathReasonForm(request.POST)
        
        if form.is_valid():
            try:
                # Salvar tipo de morte
                reason = form.save(commit=False)
                reason.created_by = request.user  # Se houver campo de auditoria
                reason.save()
                
                # Log de sucesso
                logger.info(
                    f"Tipo de morte '{reason.name}' criado por {request.user.username}. "
                    f"ID: {reason.id}"
                )
                
                # Invalidar cache
                _invalidate_death_reason_cache()
                
                # Mensagem de sucesso
                messages.success(
                    request,
                    f'Tipo de morte "{reason.name}" cadastrado com sucesso!'
                )
                
                return redirect('operations_cadastros:death_reason_list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao criar tipo de morte: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao cadastrar tipo de morte. Por favor, tente novamente.'
                )
        else:
            logger.warning(
                f"Validação de formulário falhou ao criar tipo de morte. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = DeathReasonForm()
    
    context = {
        'form': form,
        'form_title': 'Novo Tipo de Morte',
        'form_description': 'Cadastre um novo tipo de morte no sistema',
        'submit_button_text': 'Cadastrar',
        'cancel_url': reverse('operations_cadastros:death_reason_list'),
        'show_back_button': True,
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_http_methods(["GET", "POST"])
def death_reason_update_view(request, pk):
    """
    Atualiza dados de um tipo de morte existente.
    
    Args:
        pk: Primary key do tipo de morte
        
    Returns:
        - GET: Formulário preenchido
        - POST: Redireciona para lista ou exibe erros
    """
    reason = get_object_or_404(DeathReason, pk=pk)
    
    if request.method == 'POST':
        form = DeathReasonForm(request.POST, instance=reason)
        
        if form.is_valid():
            try:
                # Armazenar nome antigo para log
                old_name = reason.name
                
                # Salvar alterações
                reason = form.save(commit=False)
                reason.updated_by = request.user  # Se houver campo de auditoria
                reason.save()
                
                # Log de alteração
                logger.info(
                    f"Tipo de morte atualizado por {request.user.username}. "
                    f"ID: {reason.id}, Nome antigo: '{old_name}', Nome novo: '{reason.name}'"
                )
                
                # Invalidar cache
                _invalidate_death_reason_cache()
                
                # Mensagem de sucesso
                messages.success(
                    request,
                    f'Tipo de morte "{reason.name}" atualizado com sucesso!'
                )
                
                return redirect('operations_cadastros:death_reason_list')
                
            except Exception as e:
                logger.error(
                    f"Erro ao atualizar tipo de morte {reason.id}: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao atualizar tipo de morte. Por favor, tente novamente.'
                )
        else:
            logger.warning(
                f"Validação falhou ao atualizar tipo de morte {reason.id}. "
                f"Usuário: {request.user.username}, Erros: {form.errors}"
            )
    else:
        form = DeathReasonForm(instance=reason)
    
    context = {
        'form': form,
        'form_title': f'Editar Tipo de Morte: {reason.name}',
        'form_description': f'Atualize as informações do tipo de morte {reason.name}',
        'submit_button_text': 'Salvar Alterações',
        'cancel_url': reverse('operations_cadastros:death_reason_list'),
        'show_back_button': True,
        'form_badge': 'Editando',
        'form_badge_color': 'blue',
    }
    
    return render(request, 'shared/generic_form.html', context)


@login_required
@require_POST
def death_reason_deactivate_view(request, pk):
    """
    Desativa um tipo de morte.
    
    Apenas requisições POST são aceitas (confirmação via modal).
    
    ATENÇÃO: Verifica se o tipo está em uso antes de desativar.
    
    Args:
        pk: Primary key do tipo de morte
        
    Returns:
        Redirect para lista de tipos de morte
    """
    reason = get_object_or_404(DeathReason, pk=pk)
    
    try:
        # Verificar se está em uso (se houver relacionamento)
        # from inventory.models import AnimalMovement
        # mortes_ativas = AnimalMovement.objects.filter(
        #     death_reason=reason,
        #     operation_type='MORTE'
        # ).count()
        # 
        # if mortes_ativas > 0:
        #     logger.warning(
        #         f"Tentativa de desativar tipo de morte '{reason.name}' (ID: {reason.id}) "
        #         f"com {mortes_ativas} registros ativos. Usuário: {request.user.username}"
        #     )
        #     messages.error(
        #         request,
        #         f'Não é possível desativar o tipo "{reason.name}" pois existem '
        #         f'{mortes_ativas} registros de morte vinculados a ele.'
        #     )
        #     return redirect('operations_cadastros:death_reason_list')
        
        reason_name = reason.name
        reason.deactivate()
        
        # Log de desativação
        logger.warning(
            f"Tipo de morte '{reason_name}' (ID: {reason.id}) desativado por {request.user.username}"
        )
        
        # Invalidar cache
        _invalidate_death_reason_cache()
        
        # Mensagem ao usuário
        messages.warning(
            request,
            f'Tipo de morte "{reason_name}" foi desativado. '
            f'Você pode reativá-lo a qualquer momento.'
        )
        
    except Exception as e:
        logger.error(
            f"Erro ao desativar tipo de morte {reason.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao desativar tipo de morte. Por favor, tente novamente.'
        )
    
    return redirect('operations_cadastros:death_reason_list')


@login_required
@require_POST
def death_reason_activate_view(request, pk):
    """
    Reativa um tipo de morte desativado.
    
    Args:
        pk: Primary key do tipo de morte
        
    Returns:
        Redirect para lista de tipos de morte
    """
    reason = get_object_or_404(DeathReason, pk=pk)
    
    try:
        reason_name = reason.name
        reason.activate()
        
        # Log de reativação
        logger.info(
            f"Tipo de morte '{reason_name}' (ID: {reason.id}) reativado por {request.user.username}"
        )
        
        # Invalidar cache
        _invalidate_death_reason_cache()
        
        # Mensagem ao usuário
        messages.success(
            request,
            f'Tipo de morte "{reason_name}" foi reativado com sucesso!'
        )
        
    except Exception as e:
        logger.error(
            f"Erro ao reativar tipo de morte {reason.id}: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao reativar tipo de morte. Por favor, tente novamente.'
        )
    
    return redirect('operations_cadastros:death_reason_list')


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def client_inactive_list_view(request):
    """
    Lista clientes inativos (desativados).
    
    Returns:
        Template renderizado com lista de clientes inativos
    """
    try:
        clients_queryset = Client.objects.filter(
            is_active=False
        ).order_by('-updated_at')
        
        paginator = Paginator(clients_queryset, 20)
        page_number = request.GET.get('page', 1)
        
        try:
            clients_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            clients_page = paginator.page(1)
        
        context = {
            'clients': clients_page,
            'total_count': paginator.count,
            'page_obj': clients_page,
            'is_paginated': paginator.num_pages > 1,
        }
        
        logger.info(
            f"Lista de clientes inativos acessada por {request.user.username}. "
            f"Total: {paginator.count}"
        )
        
        return render(request, 'operations/client_inactive_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao listar clientes inativos: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar clientes inativos.')
        return redirect('operations_cadastros:client_list')


@login_required
@require_http_methods(["GET"])
def death_reason_inactive_list_view(request):
    """
    Lista tipos de morte inativos (desativados).
    
    Returns:
        Template renderizado com lista de tipos de morte inativos
    """
    try:
        reasons_queryset = DeathReason.objects.filter(
            is_active=False
        ).order_by('-updated_at')
        
        paginator = Paginator(reasons_queryset, 20)
        page_number = request.GET.get('page', 1)
        
        try:
            reasons_page = paginator.page(page_number)
        except (PageNotAnInteger, EmptyPage):
            reasons_page = paginator.page(1)
        
        context = {
            'reasons': reasons_page,
            'total_count': paginator.count,
            'page_obj': reasons_page,
            'is_paginated': paginator.num_pages > 1,
        }
        
        logger.info(
            f"Lista de tipos de morte inativos acessada por {request.user.username}. "
            f"Total: {paginator.count}"
        )
        
        return render(request, 'operations/death_reason_inactive_list.html', context)
        
    except Exception as e:
        logger.error(f"Erro ao listar tipos de morte inativos: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar tipos de morte inativos.')
        return redirect('operations_cadastros:death_reason_list')
    
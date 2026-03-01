"""
Core Views — Dashboard + Registro + Aprovação de usuário.

Responsabilidades:
- Registro de novos usuários (aguardando aprovação)
- Aprovação/Rejeição de usuários via token por email
- Dashboard com métricas e gráficos do sistema
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from datetime import date, timedelta
from typing import Dict, List, Optional
import json
import logging

from farms.models import Farm
from inventory.models import AnimalCategory, FarmStockBalance, AnimalMovement
from inventory.domain.value_objects import OperationType
from core.forms import RegisterForm
from core.tokens import validar_token
from core.emails import (
    notificar_staff_novo_cadastro,
    notificar_usuario_aprovado,
    notificar_usuario_rejeitado,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def _is_staff_or_super(user) -> bool:
    """Verifica se usuário é staff ou superusuário."""
    return user.is_active and (user.is_staff or user.is_superuser)


def _get_mes_atual_info() -> Dict:
    """Retorna informações sobre o mês atual."""
    today = date.today()
    primeiro_dia_mes = today.replace(day=1)
    inicio_mes = timezone.make_aware(
        timezone.datetime.combine(primeiro_dia_mes, timezone.datetime.min.time())
    )

    return {
        'today': today,
        'primeiro_dia_mes': primeiro_dia_mes,
        'inicio_mes': inicio_mes,
        'nome_mes': primeiro_dia_mes.strftime('%B de %Y'),
    }


# ══════════════════════════════════════════════════════════════════
# REGISTRO DE USUÁRIO
# ══════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Cadastro público de novos usuários.

    Workflow:
    1. Usuário preenche formulário de registro
    2. Conta é criada como inativa (is_active=False)
    3. Email é enviado para todos os administradores
    4. Administrador aprova/rejeita via link no email

    Returns:
        - GET: Renderiza formulário de registro
        - POST: Processa registro e redireciona para login
    """
    if request.user.is_authenticated:
        messages.info(request, 'Você já está autenticado no sistema.')
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)

        if form.is_valid():
            try:
                usuario = form.save()
                enviados = notificar_staff_novo_cadastro(request, usuario)

                logger.info(
                    f"Novo cadastro realizado: {usuario.username} ({usuario.email}). "
                    f"{enviados} administrador(es) notificado(s)."
                )

                messages.success(
                    request,
                    'Cadastro realizado com sucesso! Aguarde a aprovação da sua conta '
                    'pelo administrador. Você receberá um email assim que sua conta for aprovada.'
                )

                return redirect('login')

            except Exception as e:
                logger.error(f"Erro ao processar registro: {str(e)}")
                messages.error(
                    request,
                    'Ocorreu um erro ao processar seu cadastro. Por favor, tente novamente.'
                )
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {
        'form': form,
        'form_title': 'Criar Nova Conta',
        'form_description': 'Preencha seus dados para solicitar acesso ao sistema',
        'submit_button_text': 'Criar Conta',
    })


# ══════════════════════════════════════════════════════════════════
# APROVAÇÃO DE USUÁRIO (via token do email)
# ══════════════════════════════════════════════════════════════════

@require_http_methods(["GET", "POST"])
def aprovar_usuario_view(request, token: str):
    """
    Processa aprovação ou rejeição de um novo usuário.

    Acessada através do link enviado ao staff por email.
    Não requer login — o token funciona como autenticação.

    Args:
        token: Token de validação único por usuário

    Query Parameters:
        acao: 'aprovar' ou 'rejeitar' (default: 'aprovar')

    POST Parameters:
        acao: 'aprovar' ou 'rejeitar'

    Returns:
        - GET: Página de confirmação da ação
        - POST: Processa ação e mostra resultado
    """
    user_id = validar_token(token)

    if user_id is None:
        logger.warning(f"Tentativa de acesso com token inválido ou expirado: {token[:20]}...")
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': 'O link expirou ou é inválido.',
            'detalhes': 'Os links de aprovação são válidos por 7 dias. Solicite um novo link ao administrador.',
        })

    try:
        usuario = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        logger.error(f"Usuário ID {user_id} não encontrado para aprovação")
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': 'Usuário não encontrado.',
            'detalhes': 'O usuário pode ter sido removido do sistema.',
        })

    if usuario.is_active:
        logger.info(f"Tentativa de aprovar usuário já ativo: {usuario.username}")
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': 'Conta já foi aprovada.',
            'detalhes': f'A conta de {usuario.get_full_name() or usuario.username} já está ativa no sistema.',
        })

    acao = request.GET.get('acao', 'aprovar')

    if request.method == 'POST':
        acao_post = request.POST.get('acao', 'aprovar')

        if acao_post == 'aprovar':
            try:
                usuario.is_active = True
                usuario.save(update_fields=['is_active'])
                notificar_usuario_aprovado(usuario)

                logger.info(f"Usuário aprovado: {usuario.username} ({usuario.email})")

                return render(request, 'registration/aprovacao_sucesso.html', {
                    'usuario': usuario,
                    'acao': 'aprovado',
                    'mensagem': f'A conta de {usuario.get_full_name() or usuario.username} foi aprovada com sucesso.',
                    'detalhes': 'O usuário recebeu um email de confirmação e já pode acessar o sistema.',
                })

            except Exception as e:
                logger.error(f"Erro ao aprovar usuário {usuario.username}: {str(e)}")
                messages.error(request, 'Erro ao aprovar usuário. Tente novamente.')
                return redirect('core:dashboard')

        elif acao_post == 'rejeitar':
            try:
                nome = usuario.get_full_name() or usuario.username
                email = usuario.email
                username = usuario.username

                notificar_usuario_rejeitado(usuario)
                usuario.delete()

                logger.info(f"Usuário rejeitado e removido: {username} ({email})")

                return render(request, 'registration/aprovacao_sucesso.html', {
                    'nome_usuario': nome,
                    'email_usuario': email,
                    'acao': 'rejeitado',
                    'mensagem': f'A solicitação de cadastro de {nome} foi rejeitada.',
                    'detalhes': 'O usuário foi notificado por email e removido do sistema.',
                })

            except Exception as e:
                logger.error(f"Erro ao rejeitar usuário {usuario.username}: {str(e)}")
                messages.error(request, 'Erro ao rejeitar usuário. Tente novamente.')
                return redirect('core:dashboard')

    return render(request, 'registration/aprovacao_confirmar.html', {
        'usuario': usuario,
        'token': token,
        'acao': acao,
        'titulo': 'Aprovar Cadastro' if acao == 'aprovar' else 'Rejeitar Cadastro',
        'mensagem': (
            f'Deseja aprovar o cadastro de {usuario.get_full_name() or usuario.username}?'
            if acao == 'aprovar' else
            f'Deseja rejeitar o cadastro de {usuario.get_full_name() or usuario.username}?'
        ),
    })


# ══════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════

# Mapeamento de OperationType → label legível
_TIPOS_LABEL = {
    OperationType.NASCIMENTO.value:            'Nascimento',
    OperationType.COMPRA.value:                'Compra',
    OperationType.DESMAME_IN.value:            'Desmame (+)',
    OperationType.DESMAME_OUT.value:           'Desmame (-)',
    OperationType.SALDO.value:                 'Ajuste de Saldo',
    OperationType.MORTE.value:                 'Morte',
    OperationType.VENDA.value:                 'Venda',
    OperationType.ABATE.value:                 'Abate',
    OperationType.DOACAO.value:                'Doação',
    OperationType.MANEJO_IN.value:             'Manejo (Entrada)',
    OperationType.MANEJO_OUT.value:            'Manejo (Saída)',
    OperationType.MUDANCA_CATEGORIA_IN.value:  'Mudança Cat. (+)',
    OperationType.MUDANCA_CATEGORIA_OUT.value: 'Mudança Cat. (-)',
}

_DASHBOARD_EMPTY_CONTEXT = {
    'total_fazendas': 0,
    'total_categorias': 0,
    'total_animais': 0,
    'movimentacoes_mes': 0,
    'mes_atual': '',
    'fazendas_saldo_json': '[]',
    'categorias_saldo_json': '[]',
    'mov_por_tipo_json': '{}',
    'labels_7dias_json': '[]',
    'entradas_7dias_json': '[]',
    'saidas_7dias_json': '[]',
    'ultimas_movimentacoes': [],
}


@login_required
def dashboard_view(request):
    """
    Dashboard principal do sistema.

    Exibe:
    - KPIs principais (total de fazendas, categorias, animais, movimentações)
    - Gráficos de distribuição (animais por fazenda, por categoria)
    - Gráfico de entradas vs saídas (últimos 7 dias)
    - Gráfico de tipos de movimentação no mês
    - Tabela das últimas movimentações

    Returns:
        Template renderizado com contexto completo
    """
    try:
        mes_info = _get_mes_atual_info()
        today = mes_info['today']
        inicio_mes = mes_info['inicio_mes']

        # ────────────────────────────────────────────────────────
        # KPIs PRINCIPAIS
        # ────────────────────────────────────────────────────────

        total_fazendas = Farm.objects.filter(is_active=True).count()
        total_categorias = AnimalCategory.objects.filter(is_active=True).count()

        total_animais = (
            FarmStockBalance.objects
            .filter(farm__is_active=True)
            .aggregate(total=Sum('current_quantity'))['total'] or 0
        )

        movimentacoes_mes = AnimalMovement.objects.filter(
            timestamp__gte=inicio_mes
        ).count()

        # ────────────────────────────────────────────────────────
        # DISTRIBUIÇÃO POR FAZENDA
        # FarmStockBalance.farm tem related_name='stock_balances'
        # ────────────────────────────────────────────────────────

        fazendas_saldo = [
            {
                'nome': farm.name,
                'saldo': farm.total_animais or 0,
            }
            for farm in Farm.objects.filter(is_active=True).annotate(
                total_animais=Sum('stock_balances__current_quantity')
            ).order_by('name')
        ]

        # ────────────────────────────────────────────────────────
        # DISTRIBUIÇÃO POR CATEGORIA
        # FarmStockBalance.animal_category tem related_name='stock_balances'
        # ────────────────────────────────────────────────────────

        categorias_saldo = [
            {
                'nome': cat.name,
                'saldo': cat.total_animais,
            }
            for cat in AnimalCategory.objects.filter(is_active=True).annotate(
                total_animais=Sum('stock_balances__current_quantity')
            ).order_by('name')
            if cat.total_animais and cat.total_animais > 0
        ]

        # ────────────────────────────────────────────────────────
        # MOVIMENTAÇÕES POR TIPO NO MÊS
        # ────────────────────────────────────────────────────────

        mov_por_tipo = {}
        for mov in (
            AnimalMovement.objects
            .filter(timestamp__gte=inicio_mes)
            .values('operation_type')
            .annotate(total=Sum('quantity'))
        ):
            total = mov['total'] or 0
            if total > 0:
                label = _TIPOS_LABEL.get(mov['operation_type'], mov['operation_type'])
                mov_por_tipo[label] = total

        # ────────────────────────────────────────────────────────
        # ENTRADAS VS SAÍDAS (ÚLTIMOS 7 DIAS)
        # ────────────────────────────────────────────────────────

        entradas_7dias, saidas_7dias, labels_7dias = [], [], []

        for i in range(6, -1, -1):
            dia = today - timedelta(days=i)
            dia_ini = timezone.make_aware(
                timezone.datetime.combine(dia, timezone.datetime.min.time())
            )
            dia_fim = timezone.make_aware(
                timezone.datetime.combine(dia, timezone.datetime.max.time())
            )

            base_qs = AnimalMovement.objects.filter(
                timestamp__gte=dia_ini,
                timestamp__lte=dia_fim,
            )

            entrada = (
                base_qs.filter(movement_type='ENTRADA')
                .aggregate(total=Sum('quantity'))['total'] or 0
            )
            saida = (
                base_qs.filter(movement_type='SAIDA')
                .aggregate(total=Sum('quantity'))['total'] or 0
            )

            entradas_7dias.append(entrada)
            saidas_7dias.append(saida)
            labels_7dias.append(dia.strftime('%d/%m'))

        # ────────────────────────────────────────────────────────
        # ÚLTIMAS MOVIMENTAÇÕES
        # ────────────────────────────────────────────────────────

        ultimas_movimentacoes = (
            AnimalMovement.objects
            .select_related(
                'farm_stock_balance__farm',
                'farm_stock_balance__animal_category',
                'created_by',
            )
            .order_by('-timestamp')[:15]
        )

        # ────────────────────────────────────────────────────────
        # CONTEXTO
        # ────────────────────────────────────────────────────────

        context = {
            # KPIs
            'total_fazendas':     total_fazendas,
            'total_categorias':   total_categorias,
            'total_animais':      total_animais,
            'movimentacoes_mes':  movimentacoes_mes,
            'mes_atual':          mes_info['nome_mes'],

            # Dados para gráficos (JSON)
            'fazendas_saldo_json':    json.dumps(fazendas_saldo,    ensure_ascii=False),
            'categorias_saldo_json':  json.dumps(categorias_saldo,  ensure_ascii=False),
            'mov_por_tipo_json':      json.dumps(mov_por_tipo,       ensure_ascii=False),
            'labels_7dias_json':      json.dumps(labels_7dias),
            'entradas_7dias_json':    json.dumps(entradas_7dias),
            'saidas_7dias_json':      json.dumps(saidas_7dias),

            # Tabela
            'ultimas_movimentacoes': ultimas_movimentacoes,
        }

        return render(request, 'core/dashboard.html', context)

    except Exception as e:
        logger.error(f"Erro ao carregar dashboard: {str(e)}", exc_info=True)
        messages.error(
            request,
            'Erro ao carregar o dashboard. Por favor, tente novamente ou contate o suporte.'
        )
        return render(request, 'core/dashboard.html', _DASHBOARD_EMPTY_CONTEXT)
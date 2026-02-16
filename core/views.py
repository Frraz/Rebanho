"""
Core Views — Dashboard + Registro + Aprovação de usuário.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.db.models import Sum
from django.utils import timezone
from datetime import date, timedelta
import json

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

# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _is_staff_or_super(user):
    return user.is_active and (user.is_staff or user.is_superuser)


# ──────────────────────────────────────────────────────────────────
# REGISTRO
# ──────────────────────────────────────────────────────────────────

def register_view(request):
    """
    Cadastro público. Cria usuário inativo e notifica staff por e-mail.
    """
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            usuario = form.save()                               # is_active=False
            enviados = notificar_staff_novo_cadastro(request, usuario)
            messages.success(
                request,
                '✅ Cadastro realizado! Aguarde a ativação da sua conta pelo administrador. '
                f'({enviados} administrador{"es" if enviados != 1 else ""} notificado{"s" if enviados != 1 else ""})'
            )
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})


# ──────────────────────────────────────────────────────────────────
# APROVAÇÃO DE USUÁRIO (link do e-mail)
# ──────────────────────────────────────────────────────────────────

def aprovar_usuario_view(request, token):
    """
    Processa aprovação ou rejeição de um novo usuário.
    Acessada pelo link enviado ao staff por e-mail.
    Não requer login — o token já é a autenticação.
    """
    user_id = validar_token(token)

    if user_id is None:
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': 'O link expirou ou é inválido. Os links de aprovação são válidos por 7 dias.'
        })

    try:
        usuario = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': 'O usuário não foi encontrado. Pode ter sido removido.'
        })

    # Usuário já processado anteriormente
    if usuario.is_active:
        return render(request, 'registration/aprovacao_invalida.html', {
            'motivo': f'A conta de {usuario.get_full_name() or usuario.username} já foi aprovada anteriormente.'
        })

    acao = request.GET.get('acao', 'aprovar')

    if request.method == 'POST':
        acao_post = request.POST.get('acao', 'aprovar')

        if acao_post == 'aprovar':
            usuario.is_active = True
            usuario.save(update_fields=['is_active'])
            notificar_usuario_aprovado(usuario)
            return render(request, 'registration/aprovacao_sucesso.html', {
                'usuario': usuario,
                'acao':    'aprovado',
            })

        elif acao_post == 'rejeitar':
            nome = usuario.get_full_name() or usuario.username
            email = usuario.email
            notificar_usuario_rejeitado(usuario)
            usuario.delete()
            return render(request, 'registration/aprovacao_sucesso.html', {
                'nome_usuario': nome,
                'acao':         'rejeitado',
            })

    # GET — exibe página de confirmação
    return render(request, 'registration/aprovacao_confirmar.html', {
        'usuario': usuario,
        'token':   token,
        'acao':    acao,
    })


# ──────────────────────────────────────────────────────────────────
# DASHBOARD
# ──────────────────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    today             = date.today()
    primeiro_dia_mes  = today.replace(day=1)
    inicio_mes        = timezone.make_aware(
        timezone.datetime.combine(primeiro_dia_mes, timezone.datetime.min.time())
    )

    total_fazendas    = Farm.objects.filter(is_active=True).count()
    total_categorias  = AnimalCategory.objects.filter(is_active=True).count()
    total_animais     = FarmStockBalance.objects.filter(
        farm__is_active=True
    ).aggregate(total=Sum('current_quantity'))['total'] or 0
    movimentacoes_mes = AnimalMovement.objects.filter(timestamp__gte=inicio_mes).count()

    fazendas_saldo = []
    for farm in Farm.objects.filter(is_active=True).order_by('name'):
        saldo = FarmStockBalance.objects.filter(
            farm=farm
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
        fazendas_saldo.append({'nome': farm.name, 'saldo': saldo})

    categorias_saldo = []
    for cat in AnimalCategory.objects.filter(is_active=True).order_by('name'):
        saldo = FarmStockBalance.objects.filter(
            animal_category=cat, farm__is_active=True
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
        categorias_saldo.append({'nome': cat.name, 'saldo': saldo})

    tipos_label = {
        OperationType.NASCIMENTO.value: 'Nascimento',
        OperationType.COMPRA.value:     'Compra',
        OperationType.DESMAME.value:    'Desmame',
        OperationType.MORTE.value:      'Morte',
        OperationType.VENDA.value:      'Venda',
        OperationType.ABATE.value:      'Abate',
        OperationType.DOACAO.value:     'Doação',
        OperationType.MANEJO_IN.value:  'Manejo (+)',
        OperationType.MANEJO_OUT.value: 'Manejo (-)',
    }
    mov_por_tipo = {}
    for op_value, op_label in tipos_label.items():
        total = AnimalMovement.objects.filter(
            timestamp__gte=inicio_mes, operation_type=op_value
        ).aggregate(total=Sum('quantity'))['total'] or 0
        if total:
            mov_por_tipo[op_label] = total

    entradas_7dias, saidas_7dias, labels_7dias = [], [], []
    for i in range(6, -1, -1):
        dia       = today - timedelta(days=i)
        dia_ini   = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.min.time()))
        dia_fim   = timezone.make_aware(timezone.datetime.combine(dia, timezone.datetime.max.time()))
        entrada   = AnimalMovement.objects.filter(
            timestamp__gte=dia_ini, timestamp__lte=dia_fim, movement_type='ENTRADA'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        saida     = AnimalMovement.objects.filter(
            timestamp__gte=dia_ini, timestamp__lte=dia_fim, movement_type='SAIDA'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        entradas_7dias.append(entrada)
        saidas_7dias.append(saida)
        labels_7dias.append(dia.strftime('%d/%m'))

    ultimas_movimentacoes = AnimalMovement.objects.select_related(
        'farm_stock_balance__farm',
        'farm_stock_balance__animal_category',
        'created_by'
    ).order_by('-timestamp')[:15]

    context = {
        'total_fazendas':        total_fazendas,
        'total_categorias':      total_categorias,
        'total_animais':         total_animais,
        'movimentacoes_mes':     movimentacoes_mes,
        'mes_atual':             primeiro_dia_mes.strftime('%B de %Y'),
        'fazendas_saldo_json':   json.dumps(fazendas_saldo, ensure_ascii=False),
        'categorias_saldo_json': json.dumps(categorias_saldo, ensure_ascii=False),
        'mov_por_tipo_json':     json.dumps(mov_por_tipo, ensure_ascii=False),
        'labels_7dias_json':     json.dumps(labels_7dias),
        'entradas_7dias_json':   json.dumps(entradas_7dias),
        'saidas_7dias_json':     json.dumps(saidas_7dias),
        'ultimas_movimentacoes': ultimas_movimentacoes,
    }
    return render(request, 'core/dashboard.html', context)
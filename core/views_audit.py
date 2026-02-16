"""
Audit Views — Painel de Auditoria do sistema.

ACESSO RESTRITO: apenas is_staff=True ou is_superuser=True.
Usuários comuns (apenas is_active=True) são redirecionados ao dashboard.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date
import calendar

from inventory.models import AnimalMovement
from farms.models import Farm

User = get_user_model()

OPERATION_LABELS = {
    'MORTE':                 ('☠️ Morte',          'red'),
    'ABATE':                 ('🔪 Abate',          'gray'),
    'VENDA':                 ('💰 Venda',          'green'),
    'DOACAO':                ('🎁 Doação',         'blue'),
    'NASCIMENTO':            ('🐣 Nascimento',     'emerald'),
    'DESMAME':               ('🍼 Desmame',        'teal'),
    'COMPRA':                ('🛒 Compra',         'indigo'),
    'SALDO':                 ('⚖️ Saldo',          'purple'),
    'MANEJO_IN':             ('🚚 Manejo (+)',     'violet'),
    'MANEJO_OUT':            ('🚚 Manejo (−)',     'orange'),
    'MUDANCA_CATEGORIA_IN':  ('🔄 Mud. Cat. (+)', 'cyan'),
    'MUDANCA_CATEGORIA_OUT': ('🔄 Mud. Cat. (−)', 'amber'),
}

COLOR_CLASSES = {
    'red':     'bg-red-100 text-red-800',
    'gray':    'bg-gray-100 text-gray-800',
    'green':   'bg-green-100 text-green-800',
    'blue':    'bg-blue-100 text-blue-800',
    'emerald': 'bg-emerald-100 text-emerald-800',
    'teal':    'bg-teal-100 text-teal-800',
    'indigo':  'bg-indigo-100 text-indigo-800',
    'purple':  'bg-purple-100 text-purple-800',
    'violet':  'bg-violet-100 text-violet-800',
    'orange':  'bg-orange-100 text-orange-800',
    'cyan':    'bg-cyan-100 text-cyan-800',
    'amber':   'bg-amber-100 text-amber-800',
}

# ── Proteção de acesso ────────────────────────────────────────────
def _pode_ver_auditoria(user):
    """Apenas staff (Membro da equipe) ou superusuário."""
    return user.is_active and (user.is_staff or user.is_superuser)


def _enrich(movement):
    label, color = OPERATION_LABELS.get(movement.operation_type, (movement.operation_type, 'gray'))
    return {
        'obj':         movement,
        'label':       label,
        'color_class': COLOR_CLASSES.get(color, 'bg-gray-100 text-gray-800'),
        'is_saida':    movement.movement_type == 'SAIDA',
    }


@login_required
@user_passes_test(_pode_ver_auditoria, login_url='/')
def audit_list_view(request):
    today = date.today()

    search    = request.GET.get('q', '').strip()
    user_id   = request.GET.get('user', '').strip()
    operation = request.GET.get('operation', '').strip()
    farm_id   = request.GET.get('farm', '').strip()
    month_str = request.GET.get('month', '').strip()
    year_str  = request.GET.get('year', '').strip()

    qs = (
        AnimalMovement.objects
        .select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'created_by', 'client', 'death_reason',
            'related_movement__farm_stock_balance__farm',
        )
        .order_by('-timestamp', '-created_at')
    )

    filtros_ativos = False

    if search:
        filtros_ativos = True
        qs = qs.filter(
            Q(farm_stock_balance__farm__name__icontains=search) |
            Q(farm_stock_balance__animal_category__name__icontains=search) |
            Q(created_by__username__icontains=search) |
            Q(created_by__first_name__icontains=search) |
            Q(created_by__last_name__icontains=search) |
            Q(client__name__icontains=search) |
            Q(death_reason__name__icontains=search)
        )
    if user_id:
        filtros_ativos = True
        qs = qs.filter(created_by_id=user_id)
    if operation:
        filtros_ativos = True
        qs = qs.filter(operation_type=operation)
    if farm_id:
        filtros_ativos = True
        qs = qs.filter(farm_stock_balance__farm_id=farm_id)
    if month_str and year_str:
        try:
            m, y  = int(month_str), int(year_str)
            start = date(y, m, 1)
            end   = date(y, m, calendar.monthrange(y, m)[1])
            qs    = qs.filter(timestamp__date__range=(start, end))
            filtros_ativos = True
        except (ValueError, TypeError):
            pass
    elif year_str:
        try:
            qs = qs.filter(timestamp__year=int(year_str))
            filtros_ativos = True
        except (ValueError, TypeError):
            pass

    total_count = qs.count()
    paginator   = Paginator(qs, 30)
    page_obj    = paginator.get_page(request.GET.get('page', 1))
    movements   = [_enrich(m) for m in page_obj]

    context = {
        'movements':      movements,
        'page_obj':       page_obj,
        'total_count':    total_count,
        'filtros_ativos': filtros_ativos,
        'search_term':    search,
        'selected_user':  user_id,
        'selected_op':    operation,
        'selected_farm':  farm_id,
        'selected_month': month_str,
        'selected_year':  year_str,
        'usuarios':       User.objects.filter(animal_movements__isnull=False).distinct().order_by('username'),
        'farms':          Farm.objects.filter(is_active=True).order_by('name'),
        'operation_types': OPERATION_LABELS,
        'months': [(1,'Janeiro'),(2,'Fevereiro'),(3,'Março'),(4,'Abril'),
                   (5,'Maio'),(6,'Junho'),(7,'Julho'),(8,'Agosto'),
                   (9,'Setembro'),(10,'Outubro'),(11,'Novembro'),(12,'Dezembro')],
        'years':  list(range(today.year - 3, today.year + 1)),
    }
    return render(request, 'core/audit_list.html', context)


@login_required
@user_passes_test(_pode_ver_auditoria, login_url='/')
def audit_detail_view(request, pk):
    movement = get_object_or_404(
        AnimalMovement.objects.select_related(
            'farm_stock_balance__farm', 'farm_stock_balance__animal_category',
            'created_by', 'client', 'death_reason',
            'related_movement__farm_stock_balance__farm',
            'related_movement__farm_stock_balance__animal_category',
        ),
        pk=pk
    )
    label, color = OPERATION_LABELS.get(movement.operation_type, (movement.operation_type, 'gray'))

    meta_map = {
        'observacao': 'Observação', 'peso': 'Peso (kg)',
        'preco_total': 'Preço Total (R$)', 'preco_unitario': 'Preço Unitário (R$)',
        'fornecedor': 'Fornecedor', 'motivo': 'Motivo',
    }
    meta_items = [(v, movement.metadata[k]) for k, v in meta_map.items() if movement.metadata.get(k)]
    meta_items += [(k.replace('_',' ').title(), v) for k, v in movement.metadata.items()
                   if k not in meta_map and v]

    context = {
        'movement':    movement,
        'op_label':    label,
        'color_class': COLOR_CLASSES.get(color, 'bg-gray-100 text-gray-800'),
        'meta_items':  meta_items,
        'is_saida':    movement.movement_type == 'SAIDA',
    }
    return render(request, 'core/audit_detail.html', context)
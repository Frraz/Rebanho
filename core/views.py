"""
Core Views - Dashboard principal.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone
from datetime import date, timedelta
import json

from farms.models import Farm
from inventory.models import AnimalCategory, FarmStockBalance, AnimalMovement
from inventory.domain.value_objects import OperationType


@login_required
def dashboard_view(request):
    today = date.today()
    primeiro_dia_mes = today.replace(day=1)
    inicio_mes = timezone.make_aware(
        timezone.datetime.combine(primeiro_dia_mes, timezone.datetime.min.time())
    )

    # ── DADOS SIMPLES (sempre carregados) ──────────────────────────
    total_fazendas = Farm.objects.filter(is_active=True).count()
    total_categorias = AnimalCategory.objects.filter(is_active=True).count()

    total_animais = FarmStockBalance.objects.filter(
        farm__is_active=True
    ).aggregate(total=Sum('current_quantity'))['total'] or 0

    movimentacoes_mes = AnimalMovement.objects.filter(
        timestamp__gte=inicio_mes
    ).count()

    # ── DADOS MÉTRICAS ──────────────────────────────────────────────

    # Saldo por fazenda
    fazendas_saldo = []
    for farm in Farm.objects.filter(is_active=True).order_by('name'):
        saldo = FarmStockBalance.objects.filter(
            farm=farm
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
        fazendas_saldo.append({'nome': farm.name, 'saldo': saldo})

    # Saldo por categoria
    categorias_saldo = []
    for cat in AnimalCategory.objects.filter(is_active=True).order_by('name'):
        saldo = FarmStockBalance.objects.filter(
            animal_category=cat,
            farm__is_active=True
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
        categorias_saldo.append({'nome': cat.name, 'saldo': saldo})

    # Movimentações por tipo no mês
    tipos_label = {
        OperationType.NASCIMENTO.value: 'Nascimento',
        OperationType.COMPRA.value: 'Compra',
        OperationType.DESMAME.value: 'Desmame',
        OperationType.MORTE.value: 'Morte',
        OperationType.VENDA.value: 'Venda',
        OperationType.ABATE.value: 'Abate',
        OperationType.DOACAO.value: 'Doação',
        OperationType.MANEJO_IN.value: 'Manejo (+)',
        OperationType.MANEJO_OUT.value: 'Manejo (-)',
    }
    mov_por_tipo = {}
    for op_value, op_label in tipos_label.items():
        total = AnimalMovement.objects.filter(
            timestamp__gte=inicio_mes,
            operation_type=op_value
        ).aggregate(total=Sum('quantity'))['total'] or 0
        if total:
            mov_por_tipo[op_label] = total

    # Entradas vs Saídas — últimos 7 dias
    entradas_7dias = []
    saidas_7dias = []
    labels_7dias = []
    for i in range(6, -1, -1):
        dia = today - timedelta(days=i)
        dia_inicio = timezone.make_aware(
            timezone.datetime.combine(dia, timezone.datetime.min.time())
        )
        dia_fim = timezone.make_aware(
            timezone.datetime.combine(dia, timezone.datetime.max.time())
        )
        entrada = AnimalMovement.objects.filter(
            timestamp__gte=dia_inicio,
            timestamp__lte=dia_fim,
            movement_type='ENTRADA'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saida = AnimalMovement.objects.filter(
            timestamp__gte=dia_inicio,
            timestamp__lte=dia_fim,
            movement_type='SAIDA'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        entradas_7dias.append(entrada)
        saidas_7dias.append(saida)
        labels_7dias.append(dia.strftime('%d/%m'))

    # Últimas 15 movimentações
    ultimas_movimentacoes = AnimalMovement.objects.select_related(
        'farm_stock_balance__farm',
        'farm_stock_balance__animal_category',
        'created_by'
    ).order_by('-timestamp')[:15]

    context = {
        # Simples
        'total_fazendas': total_fazendas,
        'total_categorias': total_categorias,
        'total_animais': total_animais,
        'movimentacoes_mes': movimentacoes_mes,
        'mes_atual': primeiro_dia_mes.strftime('%B de %Y'),

        # Métricas (JSON para Chart.js)
        'fazendas_saldo_json': json.dumps(fazendas_saldo, ensure_ascii=False),
        'categorias_saldo_json': json.dumps(categorias_saldo, ensure_ascii=False),
        'mov_por_tipo_json': json.dumps(mov_por_tipo, ensure_ascii=False),
        'labels_7dias_json': json.dumps(labels_7dias),
        'entradas_7dias_json': json.dumps(entradas_7dias),
        'saidas_7dias_json': json.dumps(saidas_7dias),
        'ultimas_movimentacoes': ultimas_movimentacoes,
    }
    return render(request, 'core/dashboard.html', context)
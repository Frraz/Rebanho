"""
Audit Views - Painel de Auditoria do sistema.

Acesso restrito: apenas is_staff=True ou is_superuser=True.

IMPORTANTE:
- A listagem usa AnimalMovement.history como fonte principal para exibir
  eventos separados (Cadastro, Edição, Remoção).
- Cancelamento continua sendo mostrado consultando o registro "live"
  correspondente (quando existir).
"""

import calendar
from datetime import date
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render

from farms.models import Farm
from inventory.models import AnimalMovement

User = get_user_model()


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITEMS_PER_PAGE = 30

MONTHS = (
    (1, "Janeiro"),
    (2, "Fevereiro"),
    (3, "Março"),
    (4, "Abril"),
    (5, "Maio"),
    (6, "Junho"),
    (7, "Julho"),
    (8, "Agosto"),
    (9, "Setembro"),
    (10, "Outubro"),
    (11, "Novembro"),
    (12, "Dezembro"),
)

OPERATION_LABELS: dict[str, tuple[str, str]] = {
    "MORTE": ("Morte", "red"),
    "ABATE": ("Abate", "gray"),
    "VENDA": ("Venda", "green"),
    "DOACAO": ("Doação", "blue"),
    "NASCIMENTO": ("Nascimento", "emerald"),
    "DESMAME_IN": ("Desmame (+)", "teal"),
    "DESMAME_OUT": ("Desmame (−)", "teal"),
    "COMPRA": ("Compra", "indigo"),
    "SALDO": ("Ajuste de Saldo", "purple"),
    "MANEJO_IN": ("Manejo (+)", "violet"),
    "MANEJO_OUT": ("Manejo (−)", "orange"),
    "MUDANCA_CATEGORIA_IN": ("Mud. Categoria (+)", "cyan"),
    "MUDANCA_CATEGORIA_OUT": ("Mud. Categoria (−)", "amber"),
}

COLOR_CLASSES: dict[str, str] = {
    "red": "bg-red-100 text-red-800",
    "gray": "bg-gray-100 text-gray-800",
    "green": "bg-green-100 text-green-800",
    "blue": "bg-blue-100 text-blue-800",
    "emerald": "bg-emerald-100 text-emerald-800",
    "teal": "bg-teal-100 text-teal-800",
    "indigo": "bg-indigo-100 text-indigo-800",
    "purple": "bg-purple-100 text-purple-800",
    "violet": "bg-violet-100 text-violet-800",
    "orange": "bg-orange-100 text-orange-800",
    "cyan": "bg-cyan-100 text-cyan-800",
    "amber": "bg-amber-100 text-amber-800",
}

EVENT_TYPE_LABELS = {
    "+": "Cadastro",
    "~": "Edição",
    "-": "Remoção",
}

_DEFAULT_COLOR = "gray"

META_LABELS: dict[str, str] = {
    "observacao": "Observação",
    "peso": "Peso (kg)",
    "preco_total": "Preço Total (R$)",
    "preco_unitario": "Preço Unitário (R$)",
    "fornecedor": "Fornecedor",
    "motivo": "Motivo",
}


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def _pode_ver_auditoria(user) -> bool:
    return user.is_active and (user.is_staff or user.is_superuser)


# ---------------------------------------------------------------------------
# Helpers (History-first)
# ---------------------------------------------------------------------------

def _history_base_queryset():
    return (
        AnimalMovement.history
        .select_related(
            "history_user",
            "farm_stock_balance__farm",
            "farm_stock_balance__animal_category",
            "created_by",
            "client",
            "death_reason",
            "related_movement__farm_stock_balance__farm",
        )
        .order_by("-history_date", "-history_id")
    )


def _apply_filters(qs, params: dict):
    filtros_ativos = False

    search = params.get("q", "").strip()
    if search:
        filtros_ativos = True
        qs = qs.filter(
            Q(farm_stock_balance__farm__name__icontains=search)
            | Q(farm_stock_balance__animal_category__name__icontains=search)
            | Q(created_by__username__icontains=search)
            | Q(created_by__first_name__icontains=search)
            | Q(created_by__last_name__icontains=search)
            | Q(client__name__icontains=search)
            | Q(death_reason__name__icontains=search)
            | Q(metadata__observacao__icontains=search)
        )

    user_id = params.get("user", "").strip()
    if user_id and user_id.isdigit():
        filtros_ativos = True
        qs = qs.filter(created_by_id=int(user_id))

    operation = params.get("operation", "").strip()
    if operation and operation in OPERATION_LABELS:
        filtros_ativos = True
        qs = qs.filter(operation_type=operation)

    farm_id = params.get("farm", "").strip()
    if farm_id and farm_id.isdigit():
        filtros_ativos = True
        qs = qs.filter(farm_stock_balance__farm_id=int(farm_id))

    month_str = params.get("month", "").strip()
    year_str = params.get("year", "").strip()

    if year_str and year_str.isdigit():
        year = int(year_str)
        if month_str and month_str.isdigit():
            month = int(month_str)
            if 1 <= month <= 12:
                start = date(year, month, 1)
                end = date(year, month, calendar.monthrange(year, month)[1])
                qs = qs.filter(history_date__date__range=(start, end))
                filtros_ativos = True
        else:
            qs = qs.filter(history_date__year=year)
            filtros_ativos = True

    return qs, filtros_ativos


def _build_prev_history_map(page_history_rows):
    """
    Para cada item da página, localiza o histórico imediatamente anterior
    para cálculo de delta (ex.: 6 → 3).
    """
    grouped = defaultdict(list)
    for row in page_history_rows:
        grouped[row.id].append(row)

    prev_map = {}
    for movement_id, rows in grouped.items():
        # menor data da página para esse id (mais antigo dentro da página)
        min_date = min(r.history_date for r in rows)
        min_history_id = min(r.history_id for r in rows if r.history_date == min_date)

        older = (
            AnimalMovement.history
            .filter(id=movement_id)
            .filter(
                Q(history_date__lt=min_date)
                | Q(history_date=min_date, history_id__lt=min_history_id)
            )
            .order_by("-history_date", "-history_id")
            .first()
        )
        if older:
            prev_map[(movement_id, min_date, min_history_id)] = older

    return prev_map


def _build_live_map(page_history_rows):
    """
    Mapa id -> movimento live (para status de cancelamento).
    """
    ids = sorted({row.id for row in page_history_rows})
    live_qs = (
        AnimalMovement.objects
        .filter(id__in=ids)
        .select_related("cancellation", "cancellation__cancelled_by")
    )
    return {m.id: m for m in live_qs}


def _serialize_history_row(row, prev_map, live_map) -> dict:
    label, color = OPERATION_LABELS.get(
        row.operation_type,
        (row.operation_type, _DEFAULT_COLOR),
    )

    key = (row.id, row.history_date, row.history_id)
    prev = prev_map.get(key)

    qty_delta = None
    if row.history_type == "~" and prev and prev.quantity != row.quantity:
        qty_delta = f"{prev.quantity} → {row.quantity}"

    live = live_map.get(row.id)
    cancellation = getattr(live, "cancellation", None) if live else None

    return {
        "obj": row,  # template usa m.obj.*
        "label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "is_saida": row.movement_type == "SAIDA",
        "cancellation": cancellation,

        "event_type": row.history_type,
        "event_badge": EVENT_TYPE_LABELS.get(row.history_type, "Evento"),
        "quantity_delta": qty_delta,
        "edited": row.history_type == "~",
        "history_user": row.history_user,
        "history_date": row.history_date,
    }


def _get_metadata_items(movement) -> list[tuple[str, str]]:
    metadata = movement.metadata or {}
    items = []

    for key, label in META_LABELS.items():
        value = metadata.get(key)
        if value:
            items.append((label, value))

    for key, value in metadata.items():
        if key not in META_LABELS and value:
            items.append((key.replace("_", " ").title(), value))

    return items


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@login_required
@user_passes_test(_pode_ver_auditoria, login_url="/")
def audit_list_view(request):
    today = date.today()
    params = request.GET

    qs = _history_base_queryset()
    qs, filtros_ativos = _apply_filters(qs, params)

    total_count = qs.count()
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(params.get("page", 1))

    page_rows = list(page_obj.object_list)
    prev_map = _build_prev_history_map(page_rows)
    live_map = _build_live_map(page_rows)

    movements = [_serialize_history_row(r, prev_map, live_map) for r in page_rows]

    context = {
        "movements": movements,
        "page_obj": page_obj,
        "total_count": total_count,
        "filtros_ativos": filtros_ativos,

        "search_term": params.get("q", "").strip(),
        "selected_user": params.get("user", "").strip(),
        "selected_op": params.get("operation", "").strip(),
        "selected_farm": params.get("farm", "").strip(),
        "selected_month": params.get("month", "").strip(),
        "selected_year": params.get("year", "").strip(),

        "usuarios": (
            User.objects
            .filter(animal_movements__isnull=False)
            .distinct()
            .order_by("username")
        ),
        "farms": Farm.objects.filter(is_active=True).order_by("name"),
        "operation_types": OPERATION_LABELS,
        "months": MONTHS,
        "years": list(range(today.year - 3, today.year + 1)),
    }
    return render(request, "core/audit_list.html", context)


@login_required
@user_passes_test(_pode_ver_auditoria, login_url="/")
def audit_detail_view(request, pk):
    movement = get_object_or_404(
        AnimalMovement.objects.select_related(
            "farm_stock_balance__farm",
            "farm_stock_balance__animal_category",
            "created_by",
            "client",
            "death_reason",
            "related_movement__farm_stock_balance__farm",
            "related_movement__farm_stock_balance__animal_category",
            "cancellation",
            "cancellation__cancelled_by",
        ),
        pk=pk,
    )

    label, color = OPERATION_LABELS.get(
        movement.operation_type,
        (movement.operation_type, _DEFAULT_COLOR),
    )

    history_entries = list(
        AnimalMovement.history
        .filter(id=movement.id)
        .select_related("history_user")
        .order_by("-history_date", "-history_id")
    )

    context = {
        "movement": movement,
        "op_label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "meta_items": _get_metadata_items(movement),
        "is_saida": movement.movement_type == "SAIDA",
        "cancellation": getattr(movement, "cancellation", None),
        "history_entries": history_entries,
    }
    return render(request, "core/audit_detail.html", context)
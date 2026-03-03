"""
Audit Views - Painel de Auditoria do sistema.

Acesso restrito: apenas is_staff=True ou is_superuser=True.
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
# Helpers
# ---------------------------------------------------------------------------

def _get_cancellation(movement):
    if hasattr(movement, "_cancellation_cache"):
        return movement._cancellation_cache
    try:
        return movement.cancellation
    except AnimalMovement.cancellation.RelatedObjectDoesNotExist:
        return None


def _build_history_map_for_page(page_movements):
    """
    Monta mapa por movement_id com o último estado histórico anterior para calcular delta.
    """
    ids = [m.id for m in page_movements]
    history_map = defaultdict(list)

    qs = (
        AnimalMovement.history
        .filter(id__in=ids)
        .order_by("id", "-history_date", "-history_id")
    )

    for h in qs:
        history_map[h.id].append(h)

    return history_map


def _compute_edit_delta(history_entries):
    """
    Retorna string de delta para exibição, ex: '6 → 3'.
    Só mostra quando último evento é edição (~) e quantidade mudou.
    """
    if not history_entries:
        return None, None

    latest = history_entries[0]
    latest_type = latest.history_type

    if latest_type != "~":
        return latest_type, None

    previous = history_entries[1] if len(history_entries) > 1 else None
    if not previous:
        return latest_type, None

    if previous.quantity != latest.quantity:
        return latest_type, f"{previous.quantity} → {latest.quantity}"

    return latest_type, None


def _enrich(movement, history_map) -> dict:
    label, color = OPERATION_LABELS.get(
        movement.operation_type,
        (movement.operation_type, _DEFAULT_COLOR),
    )

    history_entries = history_map.get(movement.id, [])
    latest_history_type, qty_delta = _compute_edit_delta(history_entries)

    event_badge = EVENT_TYPE_LABELS.get(latest_history_type, "Cadastro")

    # quem/quando da última mudança de histórico (se houver)
    history_user = None
    history_date = None
    if history_entries:
        latest_h = history_entries[0]
        history_user = latest_h.history_user
        history_date = latest_h.history_date

    return {
        "obj": movement,
        "label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "is_saida": movement.movement_type == "SAIDA",
        "cancellation": _get_cancellation(movement),

        # NOVO: auditoria de edição
        "event_type": latest_history_type or "+",
        "event_badge": event_badge,  # Cadastro / Edição / Remoção
        "quantity_delta": qty_delta,  # ex: "6 → 3"
        "edited": latest_history_type == "~",
        "history_user": history_user,
        "history_date": history_date,
    }


def _base_queryset():
    return (
        AnimalMovement.objects
        .select_related(
            "farm_stock_balance__farm",
            "farm_stock_balance__animal_category",
            "created_by",
            "client",
            "death_reason",
            "related_movement__farm_stock_balance__farm",
            "cancellation",
            "cancellation__cancelled_by",
        )
        .order_by("-timestamp", "-created_at")
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
    if farm_id:
        filtros_ativos = True
        qs = qs.filter(farm_stock_balance__farm_id=farm_id)

    month_str = params.get("month", "").strip()
    year_str = params.get("year", "").strip()

    if year_str and year_str.isdigit():
        year = int(year_str)
        if month_str and month_str.isdigit():
            month = int(month_str)
            if 1 <= month <= 12:
                start = date(year, month, 1)
                end = date(year, month, calendar.monthrange(year, month)[1])
                qs = qs.filter(timestamp__date__range=(start, end))
                filtros_ativos = True
        else:
            qs = qs.filter(timestamp__year=year)
            filtros_ativos = True

    return qs, filtros_ativos


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

    qs = _base_queryset()
    qs, filtros_ativos = _apply_filters(qs, params)

    total_count = qs.count()
    paginator = Paginator(qs, ITEMS_PER_PAGE)
    page_obj = paginator.get_page(params.get("page", 1))

    # histórico só da página atual (eficiente)
    history_map = _build_history_map_for_page(page_obj.object_list)
    movements = [_enrich(m, history_map) for m in page_obj.object_list]

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

    # histórico completo do item para detalhe (timeline)
    history_entries = list(
        AnimalMovement.history
        .filter(id=movement.id)
        .order_by("-history_date", "-history_id")
    )

    context = {
        "movement": movement,
        "op_label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "meta_items": _get_metadata_items(movement),
        "is_saida": movement.movement_type == "SAIDA",
        "cancellation": _get_cancellation(movement),
        "history_entries": history_entries,  # opcional para mostrar timeline no detail
    }
    return render(request, "core/audit_detail.html", context)
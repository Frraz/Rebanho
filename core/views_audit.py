"""
Audit Views - Painel de Auditoria do sistema.

Acesso restrito: apenas is_staff=True ou is_superuser=True.

FONTE DE DADOS: AnimalMovement (tabela live) — garantia de que TODOS os
registros aparecem, inclusive os criados antes da ativação do simple_history.
O histórico (AnimalMovement.history) é consultado apenas para enriquecer
cada item com informações de edição (quem editou, quando, delta de qty).
"""

import calendar
import logging
from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils.dateparse import parse_datetime

from farms.models import Farm
from inventory.models import AnimalMovement

User = get_user_model()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITEMS_PER_PAGE = 30

MONTHS = (
    (1, "Janeiro"), (2, "Fevereiro"), (3, "Março"), (4, "Abril"),
    (5, "Maio"), (6, "Junho"), (7, "Julho"), (8, "Agosto"),
    (9, "Setembro"), (10, "Outubro"), (11, "Novembro"), (12, "Dezembro"),
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
# Helpers — baseados na tabela LIVE (AnimalMovement)
# ---------------------------------------------------------------------------

def _get_cancellation(movement):
    """Retorna o objeto cancellation ou None (sem disparar exceção)."""
    try:
        return movement.cancellation
    except Exception:
        return None


def _base_queryset():
    """QuerySet principal — tabela live, com todos os relacionamentos."""
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


def _build_history_map(page_movements):
    """
    Consulta a tabela de histórico para os movimentos da página atual.
    Retorna dict: movement_id -> lista de entradas histórico (mais recente primeiro).
    Usado para detectar edições e calcular deltas.
    """
    ids = [m.id for m in page_movements]
    if not ids:
        return {}

    history_map = {}
    try:
        qs = (
            AnimalMovement.history
            .filter(id__in=ids)
            .select_related("history_user")
            .order_by("id", "-history_date", "-history_id")
        )
        for h in qs:
            history_map.setdefault(h.id, []).append(h)
    except Exception:
        logger.debug("Tabela de histórico indisponível — ignorando enriquecimento.")

    return history_map


def _detect_edit_info(movement, history_entries):
    """
    Detecta se houve edição usando DUAS fontes (ambas são verificadas):

    Fonte 1 — simple_history (history_type == "~"):
        Funciona quando save() é chamado (não é o caso dos services atuais).

    Fonte 2 — metadata._edited_by:
        Gravado pelos services via QuerySet.update(). Esta é a fonte
        PRINCIPAL no fluxo atual do sistema.

    Retorna: (was_edited, event_badge, qty_delta, edit_user, edit_date)
    """
    was_edited = False
    event_badge = "Cadastro"
    qty_delta = None
    edit_user = None
    edit_date = None

    # ── Fonte 1: simple_history (quando model.save() gera entrada "~")
    if history_entries:
        for entry in history_entries:
            if entry.history_type == "~":
                was_edited = True
                event_badge = "Edição"
                edit_user = entry.history_user
                edit_date = entry.history_date

                # Calcular delta: encontrar a entrada imediatamente anterior
                idx = history_entries.index(entry)
                if idx + 1 < len(history_entries):
                    previous = history_entries[idx + 1]
                    if previous.quantity != entry.quantity:
                        qty_delta = f"{previous.quantity} → {entry.quantity}"
                break  # pega a edição mais recente

    # ── Fonte 2: metadata._edited_by (QuerySet.update — fonte principal)
    # Sempre verificar, mesmo que Fonte 1 já tenha encontrado edição,
    # pois o metadata pode ter informações mais recentes.
    meta = movement.metadata or {}
    edited_by_username = meta.get("_edited_by")

    if edited_by_username:
        # Se a Fonte 1 não detectou edição, usar os dados do metadata
        if not was_edited:
            was_edited = True
            event_badge = "Edição"

            try:
                edit_user = User.objects.get(username=edited_by_username)
            except User.DoesNotExist:
                edit_user = None

            edit_date_str = meta.get("_edited_at")
            if edit_date_str:
                edit_date = parse_datetime(edit_date_str)

        # Delta de quantidade via metadata (sempre mais confiável para
        # edições via QuerySet.update, pois o service grava o valor anterior)
        qty_before = meta.get("_qty_before_edit")
        if qty_before is not None:
            try:
                qty_before_int = int(qty_before)
                if qty_before_int != movement.quantity:
                    qty_delta = f"{qty_before_int} → {movement.quantity}"
            except (ValueError, TypeError):
                pass

    return was_edited, event_badge, qty_delta, edit_user, edit_date


def _enrich(movement, history_map) -> dict:
    """Enriquece um movimento live com dados de auditoria."""
    label, color = OPERATION_LABELS.get(
        movement.operation_type,
        (movement.operation_type, _DEFAULT_COLOR),
    )

    history_entries = history_map.get(movement.id, [])
    was_edited, event_badge, qty_delta, edit_user, edit_date = _detect_edit_info(
        movement, history_entries
    )

    return {
        "obj": movement,
        "label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "is_saida": movement.movement_type == "SAIDA",
        "cancellation": _get_cancellation(movement),

        # Auditoria de edição
        "event_badge": event_badge,
        "quantity_delta": qty_delta,
        "edited": was_edited,
        "history_user": edit_user,
        "history_date": edit_date,
    }


def _get_metadata_items(movement) -> list[tuple[str, str]]:
    """Extrai metadados para exibição, filtrando campos internos (_prefixo)."""
    metadata = movement.metadata or {}
    items = []

    for key, label in META_LABELS.items():
        value = metadata.get(key)
        if value:
            items.append((label, value))

    for key, value in metadata.items():
        if key not in META_LABELS and value and not key.startswith("_"):
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

    # Enriquecer com dados de histórico (apenas para a página atual)
    history_map = _build_history_map(page_obj.object_list)
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

    # Histórico completo do item para timeline no detalhe
    history_entries = []
    try:
        history_entries = list(
            AnimalMovement.history
            .filter(id=movement.id)
            .select_related("history_user")
            .order_by("-history_date", "-history_id")
        )
    except Exception:
        pass

    # Detectar edição via ambas as fontes
    was_edited, event_badge, qty_delta, edit_user, edit_date = _detect_edit_info(
        movement, history_entries
    )

    # Metadados internos de auditoria para exibição no detail
    meta = movement.metadata or {}

    context = {
        "movement": movement,
        "op_label": label,
        "color_class": COLOR_CLASSES.get(color, COLOR_CLASSES[_DEFAULT_COLOR]),
        "meta_items": _get_metadata_items(movement),
        "is_saida": movement.movement_type == "SAIDA",
        "cancellation": _get_cancellation(movement),
        "history_entries": history_entries,

        # Dados de edição unificados
        "was_edited": was_edited,
        "event_badge": event_badge,
        "qty_delta": qty_delta,
        "edit_user": edit_user,
        "edit_date": edit_date,

        # Fallback metadata raw (para debug ou exibição extra)
        "meta_edited_by": meta.get("_edited_by"),
        "meta_edited_at": meta.get("_edited_at"),
        "meta_qty_before": meta.get("_qty_before_edit"),
    }
    return render(request, "core/audit_detail.html", context)
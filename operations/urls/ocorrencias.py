"""
operations/urls/ocorrencias.py
"""

from django.urls import path
from operations.views import ocorrencias

app_name = 'ocorrencias'

urlpatterns = [

    # ── Listagem ──────────────────────────────────────────────────────────────
    path(
        '',
        ocorrencias.occurrence_list_view,
        name='list'
    ),

    # ── Registro de ocorrências ───────────────────────────────────────────────
    path(
        'morte/',
        ocorrencias.morte_create_view,
        name='morte'
    ),
    path(
        'abate/',
        ocorrencias.abate_create_view,
        name='abate'
    ),
    path(
        'venda/',
        ocorrencias.venda_create_view,
        name='venda'
    ),
    path(
        'doacao/',
        ocorrencias.doacao_create_view,
        name='doacao'
    ),

    # ── Edição ────────────────────────────────────────────────────────────────
    path(
        '<uuid:pk>/editar/',
        ocorrencias.occurrence_edit_view,
        name='editar',
    ),

    # ── Cancelamento (estorno) ────────────────────────────────────────────────
    # POST only — @require_http_methods(["POST"]) na view
    # UUID garante que apenas IDs válidos chegam ao banco
    path(
        '<uuid:pk>/cancelar/',
        ocorrencias.occurrence_cancel_view,
        name='cancelar'
    ),
]
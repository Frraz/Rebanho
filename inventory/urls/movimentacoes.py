"""
Inventory Movimentações URLs - Rotas de Movimentação de Estoque.
"""

from django.urls import path
from inventory.views import movimentacoes

app_name = 'movimentacoes'

urlpatterns = [

    # ══════════════════════════════════════════════════════════════════════════
    # LISTAGEM E HISTÓRICO
    # ══════════════════════════════════════════════════════════════════════════
    path(
        '',
        movimentacoes.movement_list_view,
        name='list'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ENTRADAS SIMPLES
    # ══════════════════════════════════════════════════════════════════════════
    path(
        'nascimento/',
        movimentacoes.nascimento_create_view,
        name='nascimento'
    ),
    path(
        'desmame/',
        movimentacoes.desmame_create_view,
        name='desmame'
    ),
    path(
        'compra/',
        movimentacoes.compra_create_view,
        name='compra'
    ),
    path(
        'ajuste-saldo/',
        movimentacoes.saldo_create_view,
        name='saldo'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # OPERAÇÕES COMPOSTAS
    # ══════════════════════════════════════════════════════════════════════════
    path(
        'manejo/',
        movimentacoes.manejo_create_view,
        name='manejo'
    ),
    path(
        'mudanca-categoria/',
        movimentacoes.mudanca_categoria_create_view,
        name='mudanca_categoria'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # CANCELAMENTO (ESTORNO)
    # POST only — protegido contra GET acidental
    # UUID garante que apenas IDs válidos chegam ao banco
    # ══════════════════════════════════════════════════════════════════════════
    path(
        '<uuid:pk>/cancelar/',
        movimentacoes.movement_cancel_view,
        name='cancelar'
    ),
    path(
        '<uuid:pk>/editar/',
        movimentacoes.movement_edit_view,
        name='editar',
    ),
]
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
    # ATENÇÃO: 'venda/' saiu daqui.
    # Vendas passaram a ter tela própria (lista + formulário multi-lote) no app
    # `finance`, montada em /ocorrencias/venda/ pelo config/urls.py. Deixar a
    # rota antiga aqui criaria dois donos para o mesmo caminho — e a venda
    # cadastrada pelo formulário antigo não teria Sale nem lançamento no
    # extrato do cliente. Use {% url 'vendas:list' %} / {% url 'vendas:create' %}.
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
    path(
        '<uuid:pk>/cancelar/',
        ocorrencias.occurrence_cancel_view,
        name='cancelar'
    ),

    # ── Exportação PDF ────────────────────────────────────────────────────────
    # GET — respeita os mesmos query params da listagem
    path(
        'exportar/pdf/',
        ocorrencias.occurrence_pdf_view,
        name='pdf'
    ),
]
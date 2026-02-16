"""
HTMX URLs — Endpoints para interações dinâmicas nos formulários.
Prefixo: /htmx/  (registrado em config/urls.py)
"""
from django.urls import path
from inventory.views.htmx_views import (
    htmx_categorias_saida,
    htmx_categorias_entrada,
    htmx_saldo_atual,
)

app_name = 'htmx'

urlpatterns = [
    # Categorias com saldo > 0 (saídas: morte, venda, abate, doação, manejo origem)
    path('categorias-saida/',  htmx_categorias_saida,  name='categorias_saida'),

    # Todas as categorias (entradas: nascimento, compra, desmame, saldo, manejo destino)
    path('categorias-entrada/', htmx_categorias_entrada, name='categorias_entrada'),

    # Badge de saldo atual (abaixo do campo quantidade)
    path('saldo-atual/',       htmx_saldo_atual,        name='saldo_atual'),
]
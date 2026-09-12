"""
finance/urls/htmx.py

Endpoints dinâmicos, montados em /htmx/financeiro/.

Prefixo próprio porque /htmx/ já aponta para inventory.urls.htmx.
"""
from django.urls import path

from finance.views import htmx

app_name = 'htmx_financeiro'

urlpatterns = [
    path('clientes/', htmx.buscar_clientes, name='clientes'),
    path('categorias-fazenda/', htmx.categorias_da_fazenda, name='categorias_fazenda'),
    path('saldo-cliente/', htmx.saldo_do_cliente, name='saldo_cliente'),
]

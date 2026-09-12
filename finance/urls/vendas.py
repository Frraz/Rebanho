"""
finance/urls/vendas.py

Montado em /ocorrencias/venda/ para que o link do menu continue o mesmo.
A diferença é que a raiz agora abre a LISTA, e não o formulário.
"""
from django.urls import path

from finance.views import vendas

app_name = 'vendas'

urlpatterns = [
    path('', vendas.venda_list_view, name='list'),
    path('nova/', vendas.venda_create_view, name='create'),
    path('<uuid:pk>/editar/', vendas.venda_edit_view, name='edit'),
    path('<uuid:pk>/apagar/', vendas.venda_delete_view, name='delete'),
    path('exportar/pdf/', vendas.venda_pdf_view, name='pdf'),
]

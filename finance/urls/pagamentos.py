"""
finance/urls/pagamentos.py

Montado em /ocorrencias/pagamentos/ — a nova aba do dropdown Ocorrências.
"""
from django.urls import path

from finance.views import pagamentos

app_name = 'pagamentos'

urlpatterns = [
    path('', pagamentos.pagamento_list_view, name='list'),
    path('novo/', pagamentos.pagamento_create_view, name='create'),
    path('<uuid:pk>/editar/', pagamentos.pagamento_edit_view, name='edit'),
    path('<uuid:pk>/apagar/', pagamentos.pagamento_delete_view, name='delete'),
    path('exportar/pdf/', pagamentos.pagamento_pdf_view, name='pdf'),
]

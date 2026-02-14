"""
Operations Ocorrências URLs.

Rotas para:
- Morte (requer tipo de morte)
- Abate
- Venda (requer cliente e peso)
- Doação (requer cliente)
"""
from django.urls import path
from operations.views import ocorrencias as views

app_name = 'ocorrencias'

urlpatterns = [
    # Lista de ocorrências (histórico)
    path('', views.occurrence_list_view, name='list'),
    
    # Morte
    path('morte/', views.morte_create_view, name='morte'),
    
    # Abate
    path('abate/', views.abate_create_view, name='abate'),
    
    # Venda
    path('venda/', views.venda_create_view, name='venda'),
    
    # Doação
    path('doacao/', views.doacao_create_view, name='doacao'),
]
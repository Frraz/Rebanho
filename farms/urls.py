"""
Farms URLs - Rotas de gerenciamento de fazendas.
"""
from django.urls import path
from . import views

app_name = 'farms'

urlpatterns = [
    # Listagem de fazendas
    path('', views.farm_list_view, name='list'),
    
    # Criar nova fazenda
    path('nova/', views.farm_create_view, name='create'),
    
    # Editar fazenda
    path('<uuid:pk>/editar/', views.farm_update_view, name='update'),
    
    # Detalhar fazenda (visualizar saldos)
    path('<uuid:pk>/', views.farm_detail_view, name='detail'),
    
    # Ativar/Desativar fazenda (soft delete)
    path('<uuid:pk>/desativar/', views.farm_deactivate_view, name='deactivate'),
    path('<uuid:pk>/ativar/', views.farm_activate_view, name='activate'),
]
"""
Operations Cadastros URLs - Clientes e Tipos de Morte.
"""
from django.urls import path
from operations.views import cadastros as views

app_name = 'operations_cadastros'

urlpatterns = [
    # Clientes
    path('clientes/', views.client_list_view, name='client_list'),
    path('clientes/novo/', views.client_create_view, name='client_create'),
    path('clientes/<uuid:pk>/editar/', views.client_update_view, name='client_update'),
    path('clientes/<uuid:pk>/desativar/', views.client_deactivate_view, name='client_deactivate'),
    path('clientes/<uuid:pk>/ativar/', views.client_activate_view, name='client_activate'),
    
    # Tipos de Morte
    path('tipos-morte/', views.death_reason_list_view, name='death_reason_list'),
    path('tipos-morte/novo/', views.death_reason_create_view, name='death_reason_create'),
    path('tipos-morte/<uuid:pk>/editar/', views.death_reason_update_view, name='death_reason_update'),
    path('tipos-morte/<uuid:pk>/desativar/', views.death_reason_deactivate_view, name='death_reason_deactivate'),
    path('tipos-morte/<uuid:pk>/ativar/', views.death_reason_activate_view, name='death_reason_activate'),
]
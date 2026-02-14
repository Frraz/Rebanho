"""
Inventory Cadastros URLs - Tipos de Animal.
"""
from django.urls import path
from inventory.views import cadastros as views

app_name = 'inventory_cadastros'

urlpatterns = [
    # Tipos de Animal
    path('tipos-animal/', views.animal_category_list_view, name='category_list'),
    path('tipos-animal/novo/', views.animal_category_create_view, name='category_create'),
    path('tipos-animal/<uuid:pk>/editar/', views.animal_category_update_view, name='category_update'),
    path('tipos-animal/<uuid:pk>/desativar/', views.animal_category_deactivate_view, name='category_deactivate'),
    path('tipos-animal/<uuid:pk>/ativar/', views.animal_category_activate_view, name='category_activate'),
]
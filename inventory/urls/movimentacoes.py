"""
Inventory Movimentações URLs.

Rotas para:
- Nascimento
- Desmame
- Saldo
- Compra
- Manejo (inclui origem e destino)
- Mudança de Categoria (inclui categoria origem e destino)
"""
from django.urls import path
from inventory.views import movimentacoes as views

app_name = 'movimentacoes'

urlpatterns = [
    # Lista de movimentações (histórico)
    path('', views.movement_list_view, name='list'),
    
    # Nascimento
    path('nascimento/', views.nascimento_create_view, name='nascimento'),
    
    # Desmame
    path('desmame/', views.desmame_create_view, name='desmame'),
    
    # Saldo
    path('saldo/', views.saldo_create_view, name='saldo'),
    
    # Compra
    path('compra/', views.compra_create_view, name='compra'),
    
    # Manejo (operação composta - saída + entrada)
    path('manejo/', views.manejo_create_view, name='manejo'),
    
    # Mudança de Categoria (operação composta - saída + entrada)
    path('mudanca-categoria/', views.mudanca_categoria_create_view, name='mudanca_categoria'),
]
"""
Reporting URLs - Relatórios.
"""
from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    # Página inicial de relatórios (escolha entre por fazenda ou consolidado)
    path('', views.report_index_view, name='index'),
    
    # Relatório por Fazenda
    path('por-fazenda/', views.farm_report_view, name='farm_report'),
    
    # Relatório Fazendas Reunidas (Consolidado)
    path('fazendas-reunidas/', views.consolidated_report_view, name='consolidated_report'),
    
    # Exportar relatório em PDF/Excel (futuro)
    # path('exportar/<str:report_type>/', views.export_report_view, name='export'),
]
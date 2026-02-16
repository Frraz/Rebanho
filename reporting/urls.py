"""
Reporting URLs.
"""
from django.urls import path
from reporting import views

app_name = 'reporting'

urlpatterns = [
    # HTML
    path('fazenda/',     views.farm_report_view,         name='farm'),
    path('consolidado/', views.consolidated_report_view, name='consolidated'),

    # PDF (mesmos parâmetros GET das views HTML)
    path('fazenda/pdf/',     views.farm_report_pdf_view,         name='farm_pdf'),
    path('consolidado/pdf/', views.consolidated_report_pdf_view, name='consolidated_pdf'),
]
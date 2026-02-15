"""
Reporting URLs.
"""
from django.urls import path
from . import views

app_name = 'reporting'

urlpatterns = [
    path('fazenda/', views.farm_report_view, name='farm'),
    path('consolidado/', views.consolidated_report_view, name='consolidated'),
]
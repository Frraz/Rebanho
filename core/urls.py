"""
Core URLs - Dashboard e autenticação.
"""
from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard_view, name='dashboard'),
    
    # Autenticação (futura implementação)
    # path('login/', views.login_view, name='login'),
    # path('logout/', views.logout_view, name='logout'),
]
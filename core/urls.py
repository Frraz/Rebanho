"""
Core URLs — Dashboard + Auditoria + Registro + Aprovação + Reset de senha.
"""
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from core import views
from core.views_audit import audit_list_view, audit_detail_view

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('', views.dashboard_view, name='dashboard'),

    # Cadastro público
    path('cadastrar/', views.register_view, name='register'),

    # Aprovação de usuário (link do e-mail — sem login obrigatório)
    path('conta/aprovar/<str:token>/', views.aprovar_usuario_view, name='aprovar_usuario'),

    # ── Reset de senha (views nativas do Django com templates customizados) ──
    path('senha/esqueci/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset.html',
            email_template_name='emails/password_reset_email.txt',
            html_email_template_name='emails/password_reset_email.html',
            subject_template_name='emails/password_reset_subject.txt',
            success_url=reverse_lazy('core:password_reset_done'),
        ),
        name='password_reset'
    ),
    path('senha/esqueci/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done'
    ),
    path('senha/redefinir/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
            success_url=reverse_lazy('core:password_reset_complete'),
        ),
        name='password_reset_confirm'
    ),
    path('senha/redefinida/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete'
    ),

    # Auditoria (proteção is_staff/superuser dentro da view)
    path('auditoria/',           audit_list_view,   name='audit_list'),
    path('auditoria/<uuid:pk>/', audit_detail_view, name='audit_detail'),
]
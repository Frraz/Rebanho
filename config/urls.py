"""
URL Configuration for Livestock Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls),

    # ← ADICIONAR: Auth própria
    path('login/', auth_views.LoginView.as_view(
        template_name='registration/login.html'
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(
        next_page='/'
    ), name='logout'),

    path('cadastros/fazendas/', include('farms.urls')),
    
    # Core (Dashboard)
    path('', include('core.urls')),
    
    # Cadastros
    path('cadastros/fazendas/', include('farms.urls')),
    path('cadastros/', include('inventory.urls.cadastros')),
    path('cadastros/', include('operations.urls.cadastros')),
    
    # Ocorrências
    path('ocorrencias/', include('operations.urls.ocorrencias')),
    
    # Movimentações
    path('movimentacoes/', include('inventory.urls.movimentacoes')),
    
    # Relatórios ← SÓ UMA VEZ, com namespace
    path('relatorios/', include('reporting.urls', namespace='reporting')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

admin.site.site_header = "Gestão de Rebanhos"
admin.site.site_title = "Sistema de Gestão de Rebanhos"
admin.site.index_title = "Painel Administrativo"
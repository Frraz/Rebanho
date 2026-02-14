"""
URL Configuration for Livestock Management System.

Estrutura de URLs:
- / -> Dashboard
- /cadastros/ -> Fazendas, Tipos de Animal, Tipos de Morte, Clientes
- /ocorrencias/ -> Morte, Abate, Venda, Doação
- /movimentacoes/ -> Nascimento, Desmame, Manejo, Mudança de Categoria, Saldo, Compra
- /relatorios/ -> Por Fazenda, Fazendas Reunidas
- /admin/ -> Django Admin
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Django Admin
    path('admin/', admin.site.urls), 
    
    # Core (Dashboard e autenticação)
    path('', include('core.urls')),
    
    # Cadastros (Fazendas, Categorias, Clientes, etc.)
    path('cadastros/fazendas/', include('farms.urls')),
    path('cadastros/', include('inventory.urls.cadastros')),  # Tipos de Animal
    path('cadastros/', include('operations.urls.cadastros')),  # Clientes e Tipos de Morte
    
    # Ocorrências (Morte, Abate, Venda, Doação)
    path('ocorrencias/', include('operations.urls.ocorrencias')),
    
    # Movimentações (Nascimento, Desmame, Manejo, etc.)
    path('movimentacoes/', include('inventory.urls.movimentacoes')),
    
    # Relatórios
    path('relatorios/', include('reporting.urls')),
]

# Servir arquivos estáticos e media em desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Django Debug Toolbar
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass

# Customização do Admin
admin.site.site_header = "Gestão de Rebanhos"
admin.site.site_title = "Sistema de Gestão de Rebanhos"
admin.site.index_title = "Painel Administrativo"
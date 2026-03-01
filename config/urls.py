"""
URL Configuration for Livestock Management System.

Estrutura de URLs do Sistema:
═══════════════════════════════════════════════════════════════════════════

AUTENTICAÇÃO & ADMINISTRAÇÃO:
- /admin/                           → Django Admin
- /login/                          → Login de usuários
- /logout/                         → Logout de usuários
- /registrar/                      → Registro de novos usuários
- /senha/                          → Recuperação de senha

DASHBOARD:
- /                                → Dashboard principal

FAZENDAS:
- /fazendas/                       → Gerenciamento de fazendas

CADASTROS:
- /cadastros/tipos-animal/         → Tipos de animal (categorias)
- /cadastros/tipos-morte/          → Tipos de morte
- /cadastros/clientes/             → Clientes

MOVIMENTAÇÕES:
- /movimentacoes/                  → Movimentações de estoque
- /movimentacoes/nascimento/       → Registro de nascimentos
- /movimentacoes/compra/           → Registro de compras
- /movimentacoes/manejo/           → Manejo entre fazendas
- /movimentacoes/mudanca-categoria/ → Mudança de categoria
- etc.

OCORRÊNCIAS:
- /ocorrencias/                    → Ocorrências (morte, venda, abate, doação)
- /ocorrencias/morte/              → Registro de mortes
- /ocorrencias/venda/              → Registro de vendas
- /ocorrencias/abate/              → Registro de abates
- /ocorrencias/doacao/             → Registro de doações

RELATÓRIOS:
- /relatorios/                     → Índice de relatórios
- /relatorios/fazenda/             → Relatório por fazenda
- /relatorios/consolidado/         → Relatório consolidado

AUDITORIA (Staff only):
- /auditoria/                      → Logs de auditoria

HTMX ENDPOINTS:
- /htmx/                           → Endpoints HTMX para interações dinâmicas

═══════════════════════════════════════════════════════════════════════════

Observações Técnicas:
- URLs organizadas por funcionalidade
- Namespaces evitam conflitos de nomes
- Ordem importa: URLs mais específicas primeiro
- Debug toolbar apenas em desenvolvimento
- Arquivos estáticos/media apenas em desenvolvimento
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.views.generic import RedirectView


# ══════════════════════════════════════════════════════════════════════════════
# CUSTOMIZAÇÃO DO ADMIN
# ══════════════════════════════════════════════════════════════════════════════

admin.site.site_header = "Gestão de Rebanhos"
admin.site.site_title = "Sistema de Gestão de Rebanhos"
admin.site.index_title = "Painel Administrativo"


# ══════════════════════════════════════════════════════════════════════════════
# URL PATTERNS PRINCIPAIS
# ══════════════════════════════════════════════════════════════════════════════

urlpatterns = [
    
    # ──────────────────────────────────────────────────────────────────────────
    # ADMINISTRAÇÃO
    # ──────────────────────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # AUTENTICAÇÃO
    # ──────────────────────────────────────────────────────────────────────────
    
    # Login
    path(
        'login/',
        auth_views.LoginView.as_view(
            template_name='registration/login.html',
            redirect_authenticated_user=True,  # Redireciona se já autenticado
        ),
        name='login'
    ),
    
    # Logout
    path(
        'logout/',
        auth_views.LogoutView.as_view(
            next_page='login',  # Redireciona para login após logout
        ),
        name='logout'
    ),
    
    # Recuperação de senha
    path(
        'senha/recuperar/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset.html',
            email_template_name='emails/password_reset_email.html',
            subject_template_name='emails/password_reset_subject.txt',
        ),
        name='password_reset'
    ),
    
    path(
        'senha/recuperar/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done'
    ),
    
    path(
        'senha/redefinir/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
        ),
        name='password_reset_confirm'
    ),
    
    path(
        'senha/redefinir/concluido/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete'
    ),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # CORE (Dashboard, Registro, Auditoria)
    # ──────────────────────────────────────────────────────────────────────────
    path('', include('core.urls')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # FAZENDAS
    # ──────────────────────────────────────────────────────────────────────────
    path('fazendas/', include('farms.urls')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # CADASTROS (Inventory + Operations)
    # ──────────────────────────────────────────────────────────────────────────
    
    # Tipos de Animal e Tipos de Morte (Inventory)
    path('cadastros/', include('inventory.urls.cadastros')),
    
    # Clientes e Tipos de Morte (Operations)
    path('cadastros/', include('operations.urls.cadastros')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # MOVIMENTAÇÕES
    # ──────────────────────────────────────────────────────────────────────────
    path('movimentacoes/', include('inventory.urls.movimentacoes')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # OCORRÊNCIAS
    # ──────────────────────────────────────────────────────────────────────────
    path('ocorrencias/', include('operations.urls.ocorrencias')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # RELATÓRIOS
    # ──────────────────────────────────────────────────────────────────────────
    path('relatorios/', include('reporting.urls')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # HTMX ENDPOINTS (Interações dinâmicas)
    # ──────────────────────────────────────────────────────────────────────────
    path('htmx/', include('inventory.urls.htmx')),
    
    
    # ──────────────────────────────────────────────────────────────────────────
    # REDIRECTS (Compatibilidade e conveniência)
    # ──────────────────────────────────────────────────────────────────────────
    
    # Redirect /home para dashboard
    path('home/', RedirectView.as_view(pattern_name='core:dashboard', permanent=False)),
    
    # Redirect /inicio para dashboard
    path('inicio/', RedirectView.as_view(pattern_name='core:dashboard', permanent=False)),
]


# ══════════════════════════════════════════════════════════════════════════════
# DESENVOLVIMENTO - DEBUG TOOLBAR E ARQUIVOS ESTÁTICOS
# ══════════════════════════════════════════════════════════════════════════════

if settings.DEBUG:
    
    # Servir arquivos estáticos e de mídia em desenvolvimento
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Django Debug Toolbar (se instalado)
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# HANDLERS DE ERRO CUSTOMIZADOS (Opcional)
# ══════════════════════════════════════════════════════════════════════════════

# Descomente e customize conforme necessário
# handler404 = 'core.views.custom_404'
# handler500 = 'core.views.custom_500'
# handler403 = 'core.views.custom_403'
# handler400 = 'core.views.custom_400'
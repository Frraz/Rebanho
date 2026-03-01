"""
Operations Cadastros URLs - Clientes e Tipos de Morte.

Estrutura de URLs:
═══════════════════════════════════════════════════════════════════════════
CLIENTES:
- /cadastros/clientes/                    → Lista de clientes ativos
- /cadastros/clientes/inativos/           → Lista de clientes arquivados
- /cadastros/clientes/criar/              → Criar novo cliente
- /cadastros/clientes/<uuid>/editar/      → Editar cliente
- /cadastros/clientes/<uuid>/desativar/   → Desativar cliente (POST)
- /cadastros/clientes/<uuid>/ativar/      → Ativar cliente (POST)

TIPOS DE MORTE:
- /cadastros/tipos-morte/                 → Lista de tipos ativos
- /cadastros/tipos-morte/inativos/        → Lista de tipos arquivados
- /cadastros/tipos-morte/criar/           → Criar novo tipo
- /cadastros/tipos-morte/<uuid>/editar/   → Editar tipo
- /cadastros/tipos-morte/<uuid>/desativar/→ Desativar tipo (POST)
- /cadastros/tipos-morte/<uuid>/ativar/   → Ativar tipo (POST)
═══════════════════════════════════════════════════════════════════════════

Observações:
- UUIDs garantem segurança e não-previsibilidade
- Ações destrutivas (desativar) apenas via POST
- Listas de inativos permitem reativação
"""

from django.urls import path
from operations.views import cadastros

app_name = 'operations_cadastros'

urlpatterns = [
    
    # ══════════════════════════════════════════════════════════════════════════
    # CLIENTES
    # ══════════════════════════════════════════════════════════════════════════
    
    # Listagem
    path('clientes/', cadastros.client_list_view, name='client_list'),
    path('clientes/inativos/', cadastros.client_inactive_list_view, name='client_inactive_list'),
    
    # CRUD
    path('clientes/criar/', cadastros.client_create_view, name='client_create'),
    path('clientes/<uuid:pk>/editar/', cadastros.client_update_view, name='client_update'),
    
    # Ações
    path('clientes/<uuid:pk>/desativar/', cadastros.client_deactivate_view, name='client_deactivate'),
    path('clientes/<uuid:pk>/ativar/', cadastros.client_activate_view, name='client_activate'),
    
    
    # ══════════════════════════════════════════════════════════════════════════
    # TIPOS DE MORTE
    # ══════════════════════════════════════════════════════════════════════════
    
    # Listagem
    path('tipos-morte/', cadastros.death_reason_list_view, name='death_reason_list'),
    path('tipos-morte/inativos/', cadastros.death_reason_inactive_list_view, name='death_reason_inactive_list'),
    
    # CRUD
    path('tipos-morte/criar/', cadastros.death_reason_create_view, name='death_reason_create'),
    path('tipos-morte/<uuid:pk>/editar/', cadastros.death_reason_update_view, name='death_reason_update'),
    
    # Ações
    path('tipos-morte/<uuid:pk>/desativar/', cadastros.death_reason_deactivate_view, name='death_reason_deactivate'),
    path('tipos-morte/<uuid:pk>/ativar/', cadastros.death_reason_activate_view, name='death_reason_activate'),
]
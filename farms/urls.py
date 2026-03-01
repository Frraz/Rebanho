"""
Farms URLs - Rotas de gerenciamento de fazendas.

Estrutura de URLs:
- /fazendas/                        → Lista de fazendas ativas
- /fazendas/inativas/               → Lista de fazendas inativas
- /fazendas/criar/                  → Criar nova fazenda
- /fazendas/<uuid>/                 → Detalhes da fazenda
- /fazendas/<uuid>/editar/          → Editar fazenda
- /fazendas/<uuid>/desativar/       → Desativar fazenda (POST)
- /fazendas/<uuid>/ativar/          → Ativar fazenda (POST)

Observações:
- UUIDs garantem IDs não sequenciais e seguros
- Ordem das URLs importa (mais específicas primeiro)
- Nomes descritivos para reverse URLs
- Ações POST para operações destrutivas
"""

from django.urls import path
from . import views

app_name = 'farms'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════════════
    # LISTAGEM
    # ══════════════════════════════════════════════════════════════════════════
    
    # Lista de fazendas ativas (página principal)
    path(
        '',
        views.farm_list_view,
        name='list'
    ),
    
    # Lista de fazendas inativas (arquivadas)
    path(
        'inativas/',
        views.farm_inactive_list_view,
        name='inactive_list'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # CRUD - Criar
    # ══════════════════════════════════════════════════════════════════════════
    
    # Criar nova fazenda
    path(
        'criar/',
        views.farm_create_view,
        name='create'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # CRUD - Editar (URLs específicas antes das genéricas)
    # ══════════════════════════════════════════════════════════════════════════
    
    # Editar fazenda existente
    path(
        '<uuid:pk>/editar/',
        views.farm_update_view,
        name='update'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # AÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    
    # Desativar fazenda (soft delete - apenas POST)
    path(
        '<uuid:pk>/desativar/',
        views.farm_deactivate_view,
        name='deactivate'
    ),
    
    # Reativar fazenda desativada (apenas POST)
    path(
        '<uuid:pk>/ativar/',
        views.farm_activate_view,
        name='activate'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # CRUD - Detalhar (sempre por último para não capturar outras rotas)
    # ══════════════════════════════════════════════════════════════════════════
    
    # Visualizar detalhes da fazenda (saldos, histórico, etc.)
    path(
        '<uuid:pk>/',
        views.farm_detail_view,
        name='detail'
    ),
]
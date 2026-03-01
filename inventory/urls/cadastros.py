"""
Inventory Cadastros URLs - Tipos de Animal (Categorias).

Estrutura de URLs:
- /cadastros/tipos-animal/                     → Lista de categorias ativas
- /cadastros/tipos-animal/inativas/            → Lista de categorias inativas
- /cadastros/tipos-animal/criar/               → Criar nova categoria
- /cadastros/tipos-animal/<uuid>/              → Detalhes da categoria (futuro)
- /cadastros/tipos-animal/<uuid>/editar/       → Editar categoria
- /cadastros/tipos-animal/<uuid>/desativar/    → Desativar categoria (POST)
- /cadastros/tipos-animal/<uuid>/ativar/       → Ativar categoria (POST)

Observações:
- UUIDs garantem IDs não sequenciais e seguros
- Ordem das URLs importa (mais específicas primeiro)
- Ações POST para operações destrutivas
- Namespace: 'inventory_cadastros'
"""

from django.urls import path
from inventory.views import cadastros

app_name = 'inventory_cadastros'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════════════
    # LISTAGEM
    # ══════════════════════════════════════════════════════════════════════════
    
    # Lista de categorias ativas (página principal)
    path(
        'tipos-animal/',
        cadastros.animal_category_list_view,
        name='category_list'
    ),
    
    # Lista de categorias inativas (arquivadas)
    path(
        'tipos-animal/inativas/',
        cadastros.animal_category_inactive_list_view,
        name='category_inactive_list'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # CRUD - Criar
    # ══════════════════════════════════════════════════════════════════════════
    
    # Criar nova categoria
    path(
        'tipos-animal/criar/',
        cadastros.animal_category_create_view,
        name='category_create'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # CRUD - Editar (URLs específicas antes das genéricas)
    # ══════════════════════════════════════════════════════════════════════════
    
    # Editar categoria existente
    path(
        'tipos-animal/<uuid:pk>/editar/',
        cadastros.animal_category_update_view,
        name='category_update'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # AÇÕES
    # ══════════════════════════════════════════════════════════════════════════
    
    # Desativar categoria (soft delete - apenas POST)
    path(
        'tipos-animal/<uuid:pk>/desativar/',
        cadastros.animal_category_deactivate_view,
        name='category_deactivate'
    ),
    
    # Reativar categoria desativada (apenas POST)
    path(
        'tipos-animal/<uuid:pk>/ativar/',
        cadastros.animal_category_activate_view,
        name='category_activate'
    ),
    
    # ══════════════════════════════════════════════════════════════════════════
    # FUTURO - Detalhes (comentado até implementação)
    # ══════════════════════════════════════════════════════════════════════════
    
    # Visualizar detalhes da categoria
    # path(
    #     'tipos-animal/<uuid:pk>/',
    #     cadastros.animal_category_detail_view,
    #     name='category_detail'
    # ),
]
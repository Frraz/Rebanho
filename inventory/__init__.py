"""
Inventory App - Controle de Estoque (Core do Sistema).

Bounded Context CENTRAL responsável por:
- Categorias de animais
- Saldos consolidados (FarmStockBalance)
- Movimentações (Ledger)
- Serviços de movimentação
- Queries de estoque

Este é o AGREGADO RAIZ do sistema.
"""

default_app_config = 'inventory.apps.InventoryConfig'
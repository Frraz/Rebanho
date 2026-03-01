"""
Inventory Movimentações URLs - Rotas de Movimentação de Estoque.

Estrutura de URLs:
- /movimentacoes/                    → Histórico de movimentações
- /movimentacoes/nascimento/         → Registrar nascimento
- /movimentacoes/desmame/            → Registrar desmame
- /movimentacoes/compra/             → Registrar compra
- /movimentacoes/ajuste-saldo/       → Ajustar saldo manualmente
- /movimentacoes/manejo/             → Transferir entre fazendas
- /movimentacoes/mudanca-categoria/  → Mudar categoria de animais

Observações:
- Manejo: Operação composta (saída origem + entrada destino)
- Mudança Categoria: Operação composta (saída categoria A + entrada categoria B)
- Ajuste de Saldo: Operação crítica - auditada e com log de warning
- Todas as operações são transacionais (atomic)
- Ocorrências (MORTE, ABATE, VENDA, DOAÇÃO) têm URLs separadas em operations.urls

Tipos de Movimentação:
═══════════════════════════════════════════════════════════════════════════
ENTRADAS:
- Nascimento: Novos animais nascidos na fazenda
- Desmame: Animais desmamados (entrada no estoque adulto)
- Compra: Aquisição de animais externos
- Ajuste de Saldo: Correção manual de inventário
- Manejo (Entrada): Recebimento de outra fazenda
- Mudança Categoria (Entrada): Recebimento de outra categoria

SAÍDAS:
- Manejo (Saída): Transferência para outra fazenda
- Mudança Categoria (Saída): Transferência para outra categoria

OPERAÇÕES COMPOSTAS (Executam automaticamente saída + entrada):
- Manejo: Remove da fazenda origem e adiciona na destino
- Mudança Categoria: Remove da categoria origem e adiciona na destino
═══════════════════════════════════════════════════════════════════════════
"""

from django.urls import path
from inventory.views import movimentacoes

app_name = 'movimentacoes'

urlpatterns = [
    
    # ══════════════════════════════════════════════════════════════════════════
    # LISTAGEM E HISTÓRICO
    # ══════════════════════════════════════════════════════════════════════════
    
    # Histórico de movimentações com filtros e paginação
    path(
        '',
        movimentacoes.movement_list_view,
        name='list'
    ),
    
    
    # ══════════════════════════════════════════════════════════════════════════
    # ENTRADAS SIMPLES
    # ══════════════════════════════════════════════════════════════════════════
    
    # Registrar nascimento de animais
    path(
        'nascimento/',
        movimentacoes.nascimento_create_view,
        name='nascimento'
    ),
    
    # Registrar desmame de animais
    path(
        'desmame/',
        movimentacoes.desmame_create_view,
        name='desmame'
    ),
    
    # Registrar compra de animais
    path(
        'compra/',
        movimentacoes.compra_create_view,
        name='compra'
    ),
    
    # Ajustar saldo manualmente (correção de inventário)
    path(
        'ajuste-saldo/',
        movimentacoes.saldo_create_view,
        name='saldo'
    ),
    
    
    # ══════════════════════════════════════════════════════════════════════════
    # OPERAÇÕES COMPOSTAS (Saída + Entrada Automáticas)
    # ══════════════════════════════════════════════════════════════════════════
    
    # Manejo: Transferir animais entre fazendas
    # Cria automaticamente: 1 movimento de saída + 1 movimento de entrada
    path(
        'manejo/',
        movimentacoes.manejo_create_view,
        name='manejo'
    ),
    
    # Mudança de Categoria: Mudar animais de categoria (ex: Bezerro → Novilho)
    # Cria automaticamente: 1 movimento de saída + 1 movimento de entrada
    path(
        'mudanca-categoria/',
        movimentacoes.mudanca_categoria_create_view,
        name='mudanca_categoria'
    ),
]
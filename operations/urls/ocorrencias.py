"""
Operations Ocorrências URLs - Morte, Abate, Venda, Doação.

Estrutura de URLs:
═══════════════════════════════════════════════════════════════════════════
LISTAGEM:
- /ocorrencias/                   → Histórico de ocorrências (com filtros)

REGISTRO DE OCORRÊNCIAS:
- /ocorrencias/morte/             → Registrar morte (requer tipo de morte)
- /ocorrencias/abate/             → Registrar abate
- /ocorrencias/venda/             → Registrar venda (requer cliente)
- /ocorrencias/doacao/            → Registrar doação (requer cliente)
═══════════════════════════════════════════════════════════════════════════

Observações:
- Todas as ocorrências são SAÍDAS definitivas do estoque
- Morte: Obrigatório informar o tipo de morte (death_reason)
- Venda: Obrigatório informar cliente e opcionalmente valor
- Doação: Obrigatório informar cliente/instituição beneficiada
- Abate: Não requer campos adicionais obrigatórios
- Todas as operações são transacionais e auditadas
"""

from django.urls import path
from operations.views import ocorrencias

app_name = 'ocorrencias'

urlpatterns = [
    
    # ══════════════════════════════════════════════════════════════════════════
    # LISTAGEM E HISTÓRICO
    # ══════════════════════════════════════════════════════════════════════════
    
    # Histórico de ocorrências com filtros (tipo, fazenda, período, busca)
    path(
        '',
        ocorrencias.occurrence_list_view,
        name='list'
    ),
    
    
    # ══════════════════════════════════════════════════════════════════════════
    # REGISTRO DE OCORRÊNCIAS
    # ══════════════════════════════════════════════════════════════════════════
    
    # Registrar morte (requer tipo de morte)
    path(
        'morte/',
        ocorrencias.morte_create_view,
        name='morte'
    ),
    
    # Registrar abate (para consumo)
    path(
        'abate/',
        ocorrencias.abate_create_view,
        name='abate'
    ),
    
    # Registrar venda (requer cliente, opcionalmente valor e peso)
    path(
        'venda/',
        ocorrencias.venda_create_view,
        name='venda'
    ),
    
    # Registrar doação (requer cliente/instituição beneficiada)
    path(
        'doacao/',
        ocorrencias.doacao_create_view,
        name='doacao'
    ),
]
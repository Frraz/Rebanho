"""
finance/urls/relatorios.py

Os dois relatórios novos, montados sob /relatorios/ junto dos existentes.

Namespace próprio (`relatorios_financeiros`) para não colidir com o
`reporting`, que já usa `reporting`.
"""
from django.urls import path

from finance.views import ajustes, exclusoes, relatorios

app_name = 'relatorios_financeiros'

urlpatterns = [
    path('fluxo-financeiro/', relatorios.fluxo_financeiro_view, name='fluxo'),
    path('fluxo-financeiro/pdf/', relatorios.fluxo_financeiro_pdf_view, name='fluxo_pdf'),
    path('saldos/', relatorios.saldos_view, name='saldos'),
    path('saldos/pdf/', relatorios.saldos_pdf_view, name='saldos_pdf'),

    # Ajuste manual de saldo — acessível a partir do relatório de Saldos.
    path('saldos/ajuste/', ajustes.ajuste_create_view, name='ajuste_create'),
    path('saldos/ajuste/<uuid:pk>/editar/', ajustes.ajuste_edit_view, name='ajuste_edit'),
    path('saldos/ajuste/<uuid:pk>/apagar/', ajustes.ajuste_delete_view, name='ajuste_delete'),

    # Histórico de exclusões — registros apagados somem das demais telas, e
    # esta é a única onde continuam consultáveis.
    path('exclusoes/', exclusoes.exclusoes_list_view, name='exclusoes'),
]

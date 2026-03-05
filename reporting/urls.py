"""
Reporting URLs - Relatórios do Sistema.
Estrutura de URLs:
═══════════════════════════════════════════════════════════════════════════
ÍNDICE:
- /relatorios/                        → Página inicial de relatórios

RELATÓRIO POR FAZENDA:
- /relatorios/fazenda/                → Visualização HTML interativa
- /relatorios/fazenda/pdf/            → Exportação em PDF

RELATÓRIO CONSOLIDADO:
- /relatorios/consolidado/            → Visualização HTML interativa
- /relatorios/consolidado/pdf/        → Exportação em PDF

FICHA DE CONTROLE MANUAL:
- /relatorios/ficha-manual/           → Página de seleção
- /relatorios/ficha-manual/pdf/       → Geração do PDF para impressão
═══════════════════════════════════════════════════════════════════════════
Parâmetros Comuns (GET):
- month (int): Mês do relatório (1-12)
- year (int): Ano do relatório
- category (uuid): Filtrar por categoria específica (opcional)

Parâmetros Específicos:
- farm (uuid): ID da fazenda (obrigatório para relatório por fazenda)
- gerar (flag): Trigger para gerar relatório consolidado

Observações:
- Views HTML e PDF compartilham mesma lógica de negócio
- PDFs são gerados server-side via WeasyPrint
- Relatórios podem ser filtrados por período e categoria
- Cache aplicado quando apropriado
"""
from django.urls import path
from reporting import views
from reporting.manual_control_views import manual_control_view, manual_control_pdf_view

app_name = 'reporting'

urlpatterns = [
    # ══════════════════════════════════════════════════════════════════════════
    # ÍNDICE DE RELATÓRIOS
    # ══════════════════════════════════════════════════════════════════════════
    # Página inicial com cards de acesso rápido aos relatórios
    path(
        '',
        views.report_index_view,
        name='index'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # RELATÓRIO POR FAZENDA
    # ══════════════════════════════════════════════════════════════════════════
    # Visualização HTML com filtros e resultado na mesma página
    path(
        'fazenda/',
        views.farm_report_view,
        name='farm'
    ),
    # Exportação em PDF (requer parâmetro 'farm')
    path(
        'fazenda/pdf/',
        views.farm_report_pdf_view,
        name='farm_pdf'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # RELATÓRIO CONSOLIDADO (Todas as Fazendas)
    # ══════════════════════════════════════════════════════════════════════════
    # Visualização HTML com filtros e resultado
    path(
        'consolidado/',
        views.consolidated_report_view,
        name='consolidated'
    ),
    # Exportação em PDF
    path(
        'consolidado/pdf/',
        views.consolidated_report_pdf_view,
        name='consolidated_pdf'
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # FICHA DE CONTROLE MANUAL
    # ══════════════════════════════════════════════════════════════════════════
    # Página de seleção (fazenda, mês, ano)
    path(
        'ficha-manual/',
        manual_control_view,
        name='manual_control'
    ),
    # Geração do PDF com duas páginas para impressão
    path(
        'ficha-manual/pdf/',
        manual_control_pdf_view,
        name='manual_control_pdf'
    ),
]
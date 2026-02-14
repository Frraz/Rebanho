"""
Reporting Views - Relatórios.

TODO: Implementar views completas com filtros e geração de relatórios
"""
from django.shortcuts import render
from django.http import HttpResponse


def report_index_view(request):
    """Página inicial de relatórios (escolha entre por fazenda ou consolidado)"""
    # TODO: Implementar página de escolha
    return HttpResponse("Relatórios - Escolha o tipo - Em desenvolvimento")


def farm_report_view(request):
    """Relatório detalhado por fazenda"""
    # TODO: Implementar relatório
    # Filtros: mês, ano, fazenda, categoria
    # Irá usar: FarmReportService
    return HttpResponse("Relatório por Fazenda - Em desenvolvimento")


def consolidated_report_view(request):
    """Relatório consolidado (fazendas reunidas)"""
    # TODO: Implementar relatório
    # Filtros: mês, ano, categoria
    # Irá usar: ConsolidatedReportService
    return HttpResponse("Relatório Fazendas Reunidas - Em desenvolvimento")
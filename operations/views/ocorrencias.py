"""
Operations Ocorrências Views - Morte, Abate, Venda, Doação.

TODO: Implementar views completas com forms e HTMX
Estas views utilizarão OccurrenceService quando implementado.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse


def occurrence_list_view(request):
    """Lista histórico de ocorrências"""
    # TODO: Implementar listagem com filtros
    return HttpResponse("Histórico de Ocorrências - Em desenvolvimento")


def morte_create_view(request):
    """Registra morte (saída com tipo de morte)"""
    # TODO: Implementar formulário
    # Campos: fazenda, categoria, quantidade, data, tipo_morte, observação
    # Irá usar: OccurrenceService.execute_morte()
    return HttpResponse("Registrar Morte - Em desenvolvimento")


def abate_create_view(request):
    """Registra abate (saída)"""
    # TODO: Implementar formulário
    # Campos: fazenda, categoria, quantidade, data, observação
    return HttpResponse("Registrar Abate - Em desenvolvimento")


def venda_create_view(request):
    """Registra venda (saída com cliente e peso)"""
    # TODO: Implementar formulário
    # Campos: fazenda, categoria, quantidade, data, cliente, peso, observação
    return HttpResponse("Registrar Venda - Em desenvolvimento")


def doacao_create_view(request):
    """Registra doação (saída com cliente)"""
    # TODO: Implementar formulário
    # Campos: fazenda, categoria, quantidade, data, cliente, observação
    return HttpResponse("Registrar Doação - Em desenvolvimento")
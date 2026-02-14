"""
Inventory Cadastros Views - Tipos de Animal.

TODO: Implementar views completas com forms e HTMX
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse

from inventory.models import AnimalCategory


def animal_category_list_view(request):
    """Lista todas as categorias de animais"""
    # TODO: Implementar listagem completa
    return HttpResponse("Lista de Tipos de Animal - Em desenvolvimento")


def animal_category_create_view(request):
    """Cria nova categoria"""
    # TODO: Implementar formulário
    return HttpResponse("Criar Tipo de Animal - Em desenvolvimento")


def animal_category_update_view(request, pk):
    """Edita categoria existente"""
    # TODO: Implementar formulário
    return HttpResponse(f"Editar Tipo de Animal {pk} - Em desenvolvimento")


def animal_category_deactivate_view(request, pk):
    """Desativa categoria (soft delete)"""
    # TODO: Implementar desativação
    return HttpResponse(f"Desativar Tipo de Animal {pk} - Em desenvolvimento")


def animal_category_activate_view(request, pk):
    """Reativa categoria"""
    # TODO: Implementar reativação
    return HttpResponse(f"Ativar Tipo de Animal {pk} - Em desenvolvimento")
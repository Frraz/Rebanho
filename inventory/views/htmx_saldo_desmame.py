"""
HTMX View: saldo_desmame

Endpoint para retornar os saldos de B. Macho e B. Fêmea
de uma fazenda, usado no formulário de desmame.

Registrado em inventory/urls/htmx.py (GET /htmx/saldo-desmame/).
"""
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.auth.decorators import login_required

from core.http import uuid_param
from inventory.models import AnimalCategory, FarmStockBalance


@login_required
def saldo_desmame_view(request):
    """
    Retorna partial HTML com saldos de B. Macho e B. Fêmea para uma fazenda.

    Query params:
        farm_id: UUID da fazenda

    Retorna:
        HTML partial renderizado (inventory/saldo_desmame.html)
    """
    farm_id = uuid_param(request, 'farm_id', 'farm')

    saldo_machos = 0
    saldo_femeas = 0

    if farm_id:
        # Buscar saldo de B. Macho
        try:
            balance_machos = FarmStockBalance.objects.select_related(
                'animal_category'
            ).get(
                farm_id=farm_id,
                animal_category__slug=AnimalCategory.SystemSlugs.BEZERRO_MACHO,
            )
            saldo_machos = balance_machos.current_quantity
        except FarmStockBalance.DoesNotExist:
            saldo_machos = 0

        # Buscar saldo de B. Fêmea
        try:
            balance_femeas = FarmStockBalance.objects.select_related(
                'animal_category'
            ).get(
                farm_id=farm_id,
                animal_category__slug=AnimalCategory.SystemSlugs.BEZERRO_FEMEA,
            )
            saldo_femeas = balance_femeas.current_quantity
        except FarmStockBalance.DoesNotExist:
            saldo_femeas = 0

    html = render_to_string(
        'inventory/saldo_desmame.html',
        {
            'farm_id': farm_id,
            'saldo_machos': saldo_machos,
            'saldo_femeas': saldo_femeas,
        },
        request=request,
    )

    return HttpResponse(html)
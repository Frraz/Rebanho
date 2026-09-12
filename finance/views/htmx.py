"""
finance/views/htmx.py

Endpoints dinâmicos das telas financeiras.

Dois padrões diferentes, de propósito:

  • BUSCA DE CLIENTE devolve HTML (fragmento de lista), como os endpoints de
    `inventory/views/htmx_views.py` — o HTMX injeta direto e não precisa de
    JavaScript nenhum para montar a lista.

  • CATEGORIAS POR FAZENDA devolve JSON. Aqui o HTML não serve: o formulário
    de venda tem N linhas e cada uma precisa do MESMO conjunto de opções. O
    endpoint antigo (`/htmx/categorias-saida/`) tem `hx-target="#id_animal_category"`,
    um id único, e só conseguiria preencher uma linha. Com JSON, o Alpine
    preenche todas de uma vez e ainda usa o saldo disponível para avisar na
    tela quando a soma das quantidades passa do estoque.
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from finance.services import BalanceService
from inventory.models import FarmStockBalance
from operations.models import Client


@login_required
@require_http_methods(["GET"])
def buscar_clientes(request):
    """
    Lista de clientes que combinam com o que está sendo digitado.

    Mostra o saldo de cada um junto do nome: na hora de lançar um pagamento,
    saber quanto o cliente deve é exatamente a informação que falta.
    """
    termo = request.GET.get('q', '').strip()

    clientes = Client.objects.filter(is_active=True)
    if termo:
        clientes = clientes.filter(name__icontains=termo)
    elif not request.GET.get('all'):
        # Sem termo e sem pedido explícito, não despeja a base inteira.
        return render(request, 'finance/partials/client_results.html', {
            'clientes': [],
            'termo': termo,
            'vazio_inicial': True,
        })

    clientes = BalanceService.annotate_balance(clientes).order_by('name')

    return render(request, 'finance/partials/client_results.html', {
        'clientes': clientes,
        'termo': termo,
        'vazio_inicial': False,
    })


@login_required
@require_http_methods(["GET"])
def categorias_da_fazenda(request):
    """
    Tipos de animal com saldo na fazenda, em JSON.

    Formato:
        {"categorias": [{"id": "...", "nome": "Bezerro", "disponivel": 12}, ...]}
    """
    farm_id = request.GET.get('farm', '').strip()
    if not farm_id:
        return JsonResponse({'categorias': []})

    try:
        saldos = (
            FarmStockBalance.objects
            .filter(farm_id=farm_id, current_quantity__gt=0, animal_category__is_active=True)
            .select_related('animal_category')
            .order_by('animal_category__display_order', 'animal_category__name')
        )
        categorias = [
            {
                'id': str(saldo.animal_category_id),
                'nome': saldo.animal_category.name,
                'disponivel': saldo.current_quantity,
            }
            for saldo in saldos
        ]
    except (ValidationError, ValueError, TypeError):
        # UUID malformado na query string. O Django levanta ValidationError
        # (não ValueError) ao filtrar por um UUID inválido — tratar só o
        # segundo deixaria passar um erro 500 numa tela de apoio.
        return JsonResponse({'categorias': []})

    return JsonResponse({'categorias': categorias})


@login_required
@require_http_methods(["GET"])
def saldo_do_cliente(request):
    """Badge com o saldo atual do cliente escolhido."""
    client_id = request.GET.get('client', '').strip()
    if not client_id:
        return render(request, 'finance/partials/client_balance.html', {'cliente': None})

    try:
        cliente = Client.objects.filter(pk=client_id).first()
    except (ValidationError, ValueError):
        cliente = None
    if cliente is None:
        return render(request, 'finance/partials/client_balance.html', {'cliente': None})

    return render(request, 'finance/partials/client_balance.html', {
        'cliente': cliente,
        'saldo': BalanceService.get_balance(cliente.id),
        'totais': BalanceService.get_totals(cliente.id),
    })

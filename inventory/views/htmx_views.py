"""
HTMX Views — Endpoints para interações dinâmicas nos formulários.

FIX: aceita tanto ?farm_id=X quanto ?farm=X para máxima compatibilidade.
O form Django envia o campo como 'farm', mas semanticamente chamamos de 'farm_id'.
"""
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from inventory.models import AnimalCategory, FarmStockBalance


def _get_farm_id(request):
    """
    Lê farm_id da query string aceitando dois nomes de parâmetro:
      - farm_id (enviado via hx-vals)
      - farm    (fallback caso venha via hx-include)
    Retorna string vazia se nenhum estiver presente ou ambos vazios.
    """
    return (
        request.GET.get('farm_id', '').strip()
        or request.GET.get('farm', '').strip()
    )


@login_required
def htmx_categorias_saida(request):
    """
    Retorna <option> tags das categorias COM saldo > 0 em uma fazenda.

    GET /htmx/categorias-saida/?farm_id=<uuid>
    GET /htmx/categorias-saida/?farm_id=<uuid>&exclude_category=<uuid>
    """
    farm_id          = _get_farm_id(request)
    exclude_category = request.GET.get('exclude_category', '').strip()

    if not farm_id:
        return HttpResponse('<option value="">Selecione uma fazenda primeiro</option>')

    try:
        balances = (
            FarmStockBalance.objects
            .filter(farm_id=farm_id, current_quantity__gt=0)
            .select_related('animal_category')
            .order_by('animal_category__name')
        )

        if exclude_category:
            balances = balances.exclude(animal_category_id=exclude_category)

        if not balances.exists():
            return HttpResponse('<option value="">Nenhum animal disponível nesta fazenda</option>')

        options = ['<option value="">Selecione a categoria...</option>']
        for balance in balances:
            options.append(
                f'<option value="{balance.animal_category.id}">'
                f'{balance.animal_category.name} '
                f'(disponível: {balance.current_quantity})'
                f'</option>'
            )
        return HttpResponse('\n'.join(options))

    except Exception as e:
        return HttpResponse(f'<option value="">Erro: {e}</option>')


@login_required
def htmx_categorias_entrada(request):
    """
    Retorna <option> tags de TODAS as categorias ativas.
    Não filtra por saldo — entradas podem ir a qualquer categoria.

    GET /htmx/categorias-entrada/
    GET /htmx/categorias-entrada/?exclude_category=<uuid>
    """
    exclude_category = request.GET.get('exclude_category', '').strip()

    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')

    if exclude_category:
        categories = categories.exclude(id=exclude_category)

    if not categories.exists():
        return HttpResponse('<option value="">Nenhuma categoria cadastrada</option>')

    options = ['<option value="">Selecione a categoria...</option>']
    for cat in categories:
        options.append(f'<option value="{cat.id}">{cat.name}</option>')

    return HttpResponse('\n'.join(options))


@login_required
def htmx_saldo_atual(request):
    """
    Retorna badge HTML com o saldo disponível de uma combinação fazenda+categoria.

    GET /htmx/saldo-atual/?farm_id=<uuid>&category_id=<uuid>
    """
    farm_id     = _get_farm_id(request)
    category_id = (
        request.GET.get('category_id', '').strip()
        or request.GET.get('animal_category', '').strip()
    )

    if not farm_id or not category_id:
        return HttpResponse('')

    try:
        balance = FarmStockBalance.objects.get(
            farm_id=farm_id,
            animal_category_id=category_id,
        )
        qty = balance.current_quantity

        if qty == 0:
            html = (
                '<span class="inline-flex items-center gap-1 text-xs font-medium '
                'text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1" '
                'data-max-quantity="0">'
                '⚠️ Sem animais disponíveis nesta fazenda'
                '</span>'
            )
        else:
            label = 'animal' if qty == 1 else 'animais'
            html = (
                f'<span class="inline-flex items-center gap-1 text-xs font-medium '
                f'text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1" '
                f'data-max-quantity="{qty}">'
                f'✓ Disponível: <strong class="ml-0.5">{qty}</strong>&nbsp;{label}'
                f'</span>'
            )
        return HttpResponse(html)

    except FarmStockBalance.DoesNotExist:
        return HttpResponse(
            '<span class="text-xs text-gray-400 italic">'
            'Combinação não encontrada no estoque'
            '</span>'
        )
    except Exception:
        return HttpResponse('')
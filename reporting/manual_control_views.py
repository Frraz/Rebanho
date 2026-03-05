# reporting/views/manual_control_views.py
"""
Views para a Ficha de Controle Manual.
- manual_control_view: página de seleção (fazenda, mês, ano)
- manual_control_pdf_view: gera o PDF com as duas páginas
"""

from datetime import date
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required

from farms.models import Farm
from inventory.models import AnimalCategory
from inventory.models.stock_balance import FarmStockBalance

MONTHS = [
    (1, 'Janeiro'),  (2, 'Fevereiro'), (3, 'Março'),
    (4, 'Abril'),    (5, 'Maio'),       (6, 'Junho'),
    (7, 'Julho'),    (8, 'Agosto'),     (9, 'Setembro'),
    (10, 'Outubro'), (11, 'Novembro'),  (12, 'Dezembro'),
]

MONTH_NAMES = {n: name for n, name in MONTHS}


def _get_years():
    current = date.today().year
    return [str(y) for y in range(current - 5, current + 2)]


def _render_pdf(template_name: str, context: dict) -> HttpResponse:
    """Gera PDF via WeasyPrint — mesmo padrão do views.py principal."""
    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string
        import logging
        logger = logging.getLogger(__name__)

        html_string = render_to_string(template_name, context)
        pdf_bytes   = HTML(string=html_string).write_pdf()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = context.get('pdf_filename', 'ficha-manual.pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except ImportError:
        return HttpResponse("WeasyPrint não está instalado.", status=501)

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(
            f"Erro ao gerar PDF da ficha manual: {e}", exc_info=True
        )
        return HttpResponse(f"Erro ao gerar PDF: {e}", status=500)


@login_required
def manual_control_view(request):
    """Página de seleção da ficha de controle manual."""
    today = date.today()
    farms = Farm.objects.filter(is_active=True).order_by('name')

    context = {
        'farms':         farms,
        'months':        MONTHS,
        'years':         _get_years(),
        'default_month': today.month,
        'default_year':  str(today.year),
    }
    return render(request, 'reporting/manual_control.html', context)


@login_required
def manual_control_pdf_view(request):
    """Gera o PDF da ficha de controle manual (duas páginas)."""
    farm_id  = request.GET.get('farm', '').strip()
    month    = int(request.GET.get('month', date.today().month))
    year_raw = str(request.GET.get('year', date.today().year)).replace(".", "").replace(",", "")
    year     = int(year_raw)

    if not farm_id:
        return HttpResponse("Fazenda não informada.", status=400)

    try:
        farm = Farm.objects.get(pk=farm_id, is_active=True)
    except Farm.DoesNotExist:
        return HttpResponse("Fazenda não encontrada.", status=404)

    # ── Estoque inicial ─────────────────────────────────────────────
    # FarmStockBalance armazena o saldo ATUAL (não histórico por mês).
    # Usamos current_quantity como saldo de referência para a ficha,
    # exibindo o estado atual do sistema no momento da impressão.
    # O cabeçalho já informa mês/ano para o usuário contextualizar.

    categories = AnimalCategory.objects.filter(
        is_active=True
    ).order_by('display_order', 'name')

    # Carrega todos os saldos da fazenda em um único query (evita N+1)
    balances = {
        b.animal_category_id: b.current_quantity
        for b in FarmStockBalance.objects.filter(farm=farm).select_related('animal_category')
    }

    stock_rows    = []
    total_initial = 0

    for cat in categories:
        initial = balances.get(cat.pk, 0)
        total_initial += initial
        stock_rows.append({
            'name':    cat.name,
            'initial': initial,
        })

    month_label = MONTH_NAMES.get(month, str(month))
    filename    = f"ficha-manual_{farm.name}_{month:02d}-{year}.pdf"

    context = {
        'farm':          farm,
        'month_label':   month_label,
        'year':          year,
        'stock_rows':    stock_rows,
        'total_initial': total_initial,
        # Iteráveis para os {% for i in blank_N %} no template
        'blank_3':       range(3),
        'blank_4':       range(4),
        'blank_5':       range(5),
        'blank_11':      range(11),
        'user':          request.user,
        'pdf_filename':  filename,
    }

    return _render_pdf('reporting/manual_control_pdf.html', context)
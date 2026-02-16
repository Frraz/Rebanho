"""
Reporting Views.

Views HTML: farm_report_view, consolidated_report_view  (inalteradas)
Views PDF:  farm_report_pdf_view, consolidated_report_pdf_view  (novas)

Estratégia PDF:
  - Mesmos parâmetros GET das views HTML
  - Mesmos services (zero duplicação de lógica)
  - Template específico para impressão (pdf_base.html)
  - WeasyPrint converte HTML → PDF server-side
  - Fallback: se WeasyPrint não instalado, retorna 501 com instrução
"""
from django.shortcuts import render
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from datetime import date
import calendar

from farms.models import Farm
from inventory.models import AnimalCategory
from reporting.services.farm_report_service import FarmReportService
from reporting.services.consolidated_report_service import ConsolidatedReportService


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_period_from_request(request):
    """Extrai e valida mês/ano da query string."""
    today = date.today()
    try:
        month = int(request.GET.get('month', today.month))
        year  = int(request.GET.get('year',  today.year))
        month = max(1, min(12, month))
        year  = max(2000, min(2100, year))
    except (ValueError, TypeError):
        month, year = today.month, today.year

    start_date = date(year, month, 1)
    end_date   = date(year, month, calendar.monthrange(year, month)[1])
    return start_date, end_date, month, year


def _period_selects(today=None):
    """Retorna listas de meses/anos para os selects de filtro."""
    if today is None:
        today = date.today()
    months = [
        (1,'Janeiro'),(2,'Fevereiro'),(3,'Março'),(4,'Abril'),
        (5,'Maio'),(6,'Junho'),(7,'Julho'),(8,'Agosto'),
        (9,'Setembro'),(10,'Outubro'),(11,'Novembro'),(12,'Dezembro'),
    ]
    years = list(range(today.year - 5, today.year + 2))
    return months, years


def _render_pdf(template_name: str, context: dict) -> HttpResponse:
    """
    Renderiza um template Django como PDF via WeasyPrint.
    Fallback com instrução de instalação se WeasyPrint não estiver disponível.
    """
    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string

        html_string = render_to_string(template_name, context)
        pdf_bytes   = HTML(string=html_string).write_pdf()

        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = context.get('pdf_filename', 'relatorio.pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except ImportError:
        return HttpResponse(
            "<h2>WeasyPrint não instalado.</h2>"
            "<p>Execute: <code>pip install weasyprint</code></p>"
            "<p>Linux: <code>sudo apt install libpango-1.0-0 libpangoft2-1.0-0</code></p>",
            status=501,
            content_type='text/html',
        )


# ── Views HTML ────────────────────────────────────────────────────────────────

@login_required
def farm_report_view(request):
    """Relatório por fazenda — filtros + resultado na mesma página."""
    farms      = Farm.objects.filter(is_active=True).order_by('name')
    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
    today      = date.today()
    months, years = _period_selects(today)

    start_date, end_date, month, year = _get_period_from_request(request)
    farm_id     = request.GET.get('farm', '')
    category_id = request.GET.get('category', '')

    report = None
    if farm_id:
        try:
            report = FarmReportService.generate_report(
                farm_id=farm_id,
                start_date=start_date,
                end_date=end_date,
                animal_category_id=category_id if category_id else None
            )
        except Exception as e:
            import traceback; traceback.print_exc()
            messages.error(request, f'Erro ao gerar relatório: {e}')

    context = {
        'farms':                farms,
        'categories':           categories,
        'report':               report,
        'selected_farm_id':     farm_id,
        'selected_category_id': category_id,
        'selected_month':       month,
        'selected_year':        year,
        'months':               months,
        'years':                years,
    }
    return render(request, 'reporting/farm_report.html', context)


@login_required
def consolidated_report_view(request):
    """Relatório consolidado de todas as fazendas."""
    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
    today      = date.today()
    months, years = _period_selects(today)

    start_date, end_date, month, year = _get_period_from_request(request)
    category_id = request.GET.get('category', '')
    gerar       = request.GET.get('gerar')

    report = None
    if gerar:
        try:
            report = ConsolidatedReportService.generate_consolidated_report(
                start_date=start_date,
                end_date=end_date,
                animal_category_id=category_id if category_id else None
            )
        except Exception as e:
            import traceback; traceback.print_exc()
            messages.error(request, f'Erro ao gerar relatório: {e}')

    context = {
        'categories':           categories,
        'report':               report,
        'selected_category_id': category_id,
        'selected_month':       month,
        'selected_year':        year,
        'months':               months,
        'years':                years,
    }
    return render(request, 'reporting/consolidated_report.html', context)


# ── Views PDF ─────────────────────────────────────────────────────────────────

@login_required
def farm_report_pdf_view(request):
    """
    Exporta o relatório por fazenda como PDF.
    Parâmetros GET: os mesmos de farm_report_view. 'farm' é obrigatório.
    """
    farm_id     = request.GET.get('farm', '')
    category_id = request.GET.get('category', '')

    if not farm_id:
        raise Http404("Parâmetro 'farm' obrigatório para exportar PDF.")

    start_date, end_date, month, year = _get_period_from_request(request)

    try:
        report = FarmReportService.generate_report(
            farm_id=farm_id,
            start_date=start_date,
            end_date=end_date,
            animal_category_id=category_id if category_id else None
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return HttpResponse(f"Erro ao gerar relatório: {e}", status=500)

    farm_slug = report['farm'].name.lower().replace(' ', '-')
    filename  = f"relatorio_{farm_slug}_{month:02d}-{year}.pdf"

    return _render_pdf('reporting/farm_report_pdf.html', {
        'report':       report,
        'user':         request.user,
        'pdf_filename': filename,
    })


@login_required
def consolidated_report_pdf_view(request):
    """
    Exporta o relatório consolidado de todas as fazendas como PDF.
    Parâmetros GET: os mesmos de consolidated_report_view.
    """
    category_id = request.GET.get('category', '')
    start_date, end_date, month, year = _get_period_from_request(request)

    try:
        report = ConsolidatedReportService.generate_consolidated_report(
            start_date=start_date,
            end_date=end_date,
            animal_category_id=category_id if category_id else None
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return HttpResponse(f"Erro ao gerar relatório consolidado: {e}", status=500)

    filename = f"relatorio_consolidado_{month:02d}-{year}.pdf"

    return _render_pdf('reporting/consolidated_report_pdf.html', {
        'report':       report,
        'user':         request.user,
        'pdf_filename': filename,
    })
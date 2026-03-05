"""
Reporting Views - Relatórios do Sistema.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, Http404
from datetime import date
import calendar
from typing import Tuple, Dict, List, Optional
import logging

from farms.models import Farm
from inventory.models import AnimalCategory
from reporting.services.farm_report_service import FarmReportService
from reporting.services.consolidated_report_service import ConsolidatedReportService

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_period_from_request(request) -> Tuple[date, date, int, int]:
    """
    Extrai e valida período (mês/ano) dos parâmetros GET.

    Returns:
        (start_date, end_date, month, year)

    Regras:
    - month=0 => ano completo
    - month 1-12 => mês específico
    """
    today = date.today()

    try:
        month = int(request.GET.get('month', today.month))
        year_raw = str(request.GET.get('year', today.year)).replace(".", "").replace(",", "")
        year = int(year_raw)

        if month != 0:
            month = max(1, min(12, month))
        year = max(2000, min(2100, year))

    except (ValueError, TypeError) as e:
        logger.warning(
            f"Parâmetros de período inválidos: {request.GET}. "
            f"Usando período atual. Erro: {str(e)}"
        )
        month, year = today.month, today.year

    if month == 0:
        start_date = date(year, 1, 1)
        end_date   = date(year, 12, 31)
    else:
        start_date = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        end_date = date(year, month, last_day)

    return start_date, end_date, month, year


def _get_period_selects(today: Optional[date] = None) -> Tuple[List, List]:
    if today is None:
        today = date.today()

    months = [
        (1, 'Janeiro'),  (2, 'Fevereiro'), (3, 'Março'),
        (4, 'Abril'),    (5, 'Maio'),       (6, 'Junho'),
        (7, 'Julho'),    (8, 'Agosto'),     (9, 'Setembro'),
        (10, 'Outubro'), (11, 'Novembro'),  (12, 'Dezembro'),
    ]
    years = list(range(today.year - 5, today.year + 2))
    return months, years


def _render_pdf(template_name: str, context: dict) -> HttpResponse:
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
        logger.error("WeasyPrint não está instalado.")
        return HttpResponse("WeasyPrint não instalado.", status=501)

    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {str(e)}. Template: {template_name}", exc_info=True)
        return HttpResponse(f"Erro ao gerar PDF: {str(e)}", status=500)


def _get_previous_month_label(period_start: date) -> str:
    """
    Retorna label do mês anterior em PT-BR.
      period_start=2026-01-01 -> "DEZEMBRO 2025"
      period_start=2026-03-01 -> "FEVEREIRO 2026"
    """
    meses = [
        'JANEIRO', 'FEVEREIRO', 'MARÇO',    'ABRIL',   'MAIO',      'JUNHO',
        'JULHO',   'AGOSTO',    'SETEMBRO', 'OUTUBRO', 'NOVEMBRO',  'DEZEMBRO',
    ]
    m, y = period_start.month, period_start.year
    prev_m = 12 if m == 1 else m - 1
    prev_y = y - 1 if m == 1 else y
    return f"{meses[prev_m - 1]} {prev_y}"


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS HTML - RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_report_view(request):
    """
    Relatório por fazenda com filtros na mesma página.
    """
    try:
        farms      = Farm.objects.filter(is_active=True).order_by('name')
        categories = AnimalCategory.objects.filter(is_active=True).order_by('name')

        today = date.today()
        months, years = _get_period_selects(today)
        start_date, end_date, month, year = _get_period_from_request(request)

        farm_id     = request.GET.get('farm', '').strip()
        category_id = request.GET.get('category', '').strip()

        report = None
        if farm_id:
            farm     = get_object_or_404(Farm, pk=farm_id, is_active=True)
            category = None
            if category_id:
                category = get_object_or_404(AnimalCategory, pk=category_id, is_active=True)

            report = FarmReportService.generate(
                farm=farm,
                start_date=start_date,
                end_date=end_date,
                category=category,
            )

        context = {
            'months':              months,
            'years':               years,
            'farms':               farms,
            'categories':          categories,
            'selected_month':      month,
            'selected_year':       year,
            'selected_farm_id':    farm_id,
            'selected_category_id': category_id,
            'report':              report,
        }
        return render(request, 'reporting/farm_report.html', context)

    except Exception as e:
        logger.error(f"Erro ao gerar relatório por fazenda: {e}", exc_info=True)
        messages.error(request, "Erro ao gerar relatório. Tente novamente.")
        return render(request, 'reporting/farm_report.html', {})


@login_required
@require_http_methods(["GET"])
def consolidated_report_view(request):
    """
    Relatório consolidado de todas as fazendas.
    Suporta month=0 para consolidar o ano inteiro.
    """
    try:
        categories = AnimalCategory.objects.filter(is_active=True).order_by('name')

        today = date.today()
        months, years = _get_period_selects(today)
        start_date, end_date, month, year = _get_period_from_request(request)

        category_id = request.GET.get('category', '').strip()
        gerar       = request.GET.get('gerar')

        report = None
        if gerar:
            try:
                report = ConsolidatedReportService.generate_consolidated_report(
                    start_date=start_date,
                    end_date=end_date,
                    animal_category_id=category_id if category_id else None,
                )
                logger.info(
                    f"Relatório consolidado gerado por {request.user.username}. "
                    f"Período: {'Ano completo' if month == 0 else f'{month}/{year}'} {year}, "
                    f"Categoria: {category_id or 'Todas'}"
                )
            except Exception as e:
                logger.error(
                    f"Erro ao gerar relatório consolidado: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True,
                )
                messages.error(request, 'Erro ao gerar relatório consolidado. Por favor, tente novamente.')

        context = {
            'categories':          categories,
            'report':              report,
            'selected_category_id': category_id,
            'selected_month':      month,    # 0 = todos os meses
            'selected_year':       year,
            'months':              months,
            'years':               years,
        }
        return render(request, 'reporting/consolidated_report.html', context)

    except Exception as e:
        logger.error(f"Erro na view de relatório consolidado: {str(e)}", exc_info=True)
        messages.error(request, 'Erro ao carregar página de relatórios. Por favor, tente novamente.')
        return render(request, 'reporting/consolidated_report.html', {
            'categories': [], 'report': None,
        })


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS PDF - EXPORTAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_report_pdf_view(request):
    """
    Gera PDF do relatório por fazenda.
    """
    start_date, end_date, month, year = _get_period_from_request(request)

    farm_id = request.GET.get('farm', '').strip()
    if not farm_id:
        raise Http404("Fazenda não informada.")

    category_id = request.GET.get('category', '').strip()
    farm        = get_object_or_404(Farm, pk=farm_id, is_active=True)

    category = None
    if category_id:
        category = get_object_or_404(AnimalCategory, pk=category_id, is_active=True)

    report = FarmReportService.generate(
        farm=farm,
        start_date=start_date,
        end_date=end_date,
        category=category,
    )

    # report.period.start funciona porque FarmReport é um dataclass
    prev_month_label = _get_previous_month_label(report.period.start)

    context = {
        'report':          report,
        'user':            request.user,
        'prev_month_label': prev_month_label,
        'pdf_filename':    f"relatorio_{farm.name}_{report.period.start.strftime('%m_%Y')}.pdf",
    }
    return _render_pdf('reporting/farm_report_pdf.html', context)


@login_required
@require_http_methods(["GET"])
def consolidated_report_pdf_view(request):
    """
    Exporta relatório consolidado como PDF.
    Suporta month=0 para PDF do ano inteiro.
    """
    try:
        category_id = request.GET.get('category', '').strip()
        start_date, end_date, month, year = _get_period_from_request(request)

        report = ConsolidatedReportService.generate_consolidated_report(
            start_date=start_date,
            end_date=end_date,
            animal_category_id=category_id if category_id else None,
        )

        filename = (
            f"relatorio_consolidado_{year}.pdf"
            if month == 0
            else f"relatorio_consolidado_{month:02d}-{year}.pdf"
        )

        logger.info(
            f"PDF de relatório consolidado gerado por {request.user.username}. "
            f"Período: {'Ano completo' if month == 0 else f'{month}/{year}'} {year}, "
            f"Arquivo: {filename}"
        )

        return _render_pdf('reporting/consolidated_report_pdf.html', {
            'report':         report,
            'user':           request.user,
            'pdf_filename':   filename,
            'selected_month': month,
            'selected_year':  year,
        })

    except Exception as e:
        logger.error(
            f"Erro ao gerar PDF consolidado: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True,
        )
        return HttpResponse(
            "Erro ao gerar relatório consolidado em PDF. Por favor, tente novamente.",
            status=500,
        )


# ══════════════════════════════════════════════════════════════════════════════
# VIEW AUXILIAR - ÍNDICE DE RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def report_index_view(request):
    """
    Página inicial de relatórios com cards e formulários rápidos.
    """
    today = date.today()
    months, years = _get_period_selects(today)

    context = {
        'farms':            Farm.objects.filter(is_active=True).order_by('name'),
        'categories':       AnimalCategory.objects.filter(is_active=True).order_by('name'),
        'months':           months,
        'years':            years,
        'default_month':    today.month,
        'default_year':     today.year,
        'total_farms':      Farm.objects.filter(is_active=True).count(),
        'total_categories': AnimalCategory.objects.filter(is_active=True).count(),
    }

    logger.info(f"Índice de relatórios acessado por {request.user.username}")
    return render(request, 'reporting/report_index.html', context)
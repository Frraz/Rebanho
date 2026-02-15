"""
Reporting Views - Relatórios via GET com filtros.
"""
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import date, datetime
import calendar

from farms.models import Farm
from inventory.models import AnimalCategory
from reporting.services.farm_report_service import FarmReportService
from reporting.services.consolidated_report_service import ConsolidatedReportService


def _get_period_from_request(request):
    """Extrai e valida mês/ano da query string."""
    today = date.today()
    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
        month = max(1, min(12, month))
        year = max(2000, min(2100, year))
    except (ValueError, TypeError):
        month, year = today.month, today.year

    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    return start_date, end_date, month, year


@login_required
def farm_report_view(request):
    """Relatório por fazenda — filtros + resultado na mesma página."""
    farms = Farm.objects.filter(is_active=True).order_by('name')
    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
    today = date.today()

    # Parâmetros de filtro
    start_date, end_date, month, year = _get_period_from_request(request)
    farm_id = request.GET.get('farm')
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
            import traceback
            traceback.print_exc()
            messages.error(request, f'Erro ao gerar relatório: {e}')

    context = {
        'farms': farms,
        'categories': categories,
        'report': report,
        'selected_farm_id': farm_id or '',
        'selected_category_id': category_id,
        'selected_month': month,
        'selected_year': year,
        'months': [
            (1,'Janeiro'), (2,'Fevereiro'), (3,'Março'), (4,'Abril'),
            (5,'Maio'), (6,'Junho'), (7,'Julho'), (8,'Agosto'),
            (9,'Setembro'), (10,'Outubro'), (11,'Novembro'), (12,'Dezembro'),
        ],
        'years': list(range(today.year - 5, today.year + 2)),
    }
    return render(request, 'reporting/farm_report.html', context)


@login_required
def consolidated_report_view(request):
    """Relatório consolidado de todas as fazendas."""
    categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
    today = date.today()

    start_date, end_date, month, year = _get_period_from_request(request)
    category_id = request.GET.get('category', '')
    gerar = request.GET.get('gerar')  # Parâmetro para acionar geração

    report = None
    if gerar:
        try:
            report = ConsolidatedReportService.generate_consolidated_report(
                start_date=start_date,
                end_date=end_date,
                animal_category_id=category_id if category_id else None
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            messages.error(request, f'Erro ao gerar relatório: {e}')

    context = {
        'categories': categories,
        'report': report,
        'selected_category_id': category_id,
        'selected_month': month,
        'selected_year': year,
        'months': [
            (1,'Janeiro'), (2,'Fevereiro'), (3,'Março'), (4,'Abril'),
            (5,'Maio'), (6,'Junho'), (7,'Julho'), (8,'Agosto'),
            (9,'Setembro'), (10,'Outubro'), (11,'Novembro'), (12,'Dezembro'),
        ],
        'years': list(range(today.year - 5, today.year + 2)),
    }
    return render(request, 'reporting/consolidated_report.html', context)
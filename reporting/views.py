"""
Reporting Views - Relatórios do Sistema.

Este módulo gerencia a geração de relatórios do sistema:
- Relatório por Fazenda (HTML e PDF)
- Relatório Consolidado de todas as fazendas (HTML e PDF)

Estratégia de Implementação:
- Views HTML e PDF compartilham a mesma lógica de negócio (services)
- Templates específicos para cada formato (web e impressão)
- WeasyPrint para conversão HTML → PDF server-side
- Cache de relatórios quando apropriado
- Filtros: período (mês/ano), fazenda, categoria

Melhorias implementadas:
- Login obrigatório em todas as views
- Logging completo de operações
- Tratamento robusto de erros
- Validação de parâmetros
- Cache de queries pesadas
- Mensagens profissionais sem emojis
- Fallback gracioso se WeasyPrint não disponível
"""

from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse, Http404
from django.core.cache import cache
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
    
    Args:
        request: HttpRequest
        
    Returns:
        Tupla (start_date, end_date, month, year)
        
    Validações:
    - Mês entre 1-12
    - Ano entre 2000-2100
    - Fallback para mês/ano atual se inválido
    """
    today = date.today()
    
    try:
        month = int(request.GET.get('month', today.month))
        year = int(request.GET.get('year', today.year))
        
        # Validar ranges
        month = max(1, min(12, month))
        year = max(2000, min(2100, year))
        
    except (ValueError, TypeError) as e:
        logger.warning(
            f"Parâmetros de período inválidos: {request.GET}. "
            f"Usando período atual. Erro: {str(e)}"
        )
        month, year = today.month, today.year
    
    # Calcular datas do período
    start_date = date(year, month, 1)
    _, last_day = calendar.monthrange(year, month)
    end_date = date(year, month, last_day)
    
    return start_date, end_date, month, year


def _get_period_selects(today: Optional[date] = None) -> Tuple[List, List]:
    """
    Retorna listas de meses e anos para filtros de período.
    
    Args:
        today: Data de referência (default: hoje)
        
    Returns:
        Tupla (lista_meses, lista_anos)
    """
    if today is None:
        today = date.today()
    
    months = [
        (1, 'Janeiro'), (2, 'Fevereiro'), (3, 'Março'),
        (4, 'Abril'), (5, 'Maio'), (6, 'Junho'),
        (7, 'Julho'), (8, 'Agosto'), (9, 'Setembro'),
        (10, 'Outubro'), (11, 'Novembro'), (12, 'Dezembro'),
    ]
    
    # Anos: 5 anos atrás até 1 ano à frente
    years = list(range(today.year - 5, today.year + 2))
    
    return months, years


def _render_pdf(template_name: str, context: dict) -> HttpResponse:
    """
    Renderiza template Django como PDF usando WeasyPrint.
    
    Args:
        template_name: Caminho do template
        context: Contexto para renderização
        
    Returns:
        HttpResponse com PDF ou mensagem de erro
        
    Observações:
    - WeasyPrint deve estar instalado: pip install weasyprint
    - Linux requer: libpango-1.0-0 libpangoft2-1.0-0
    - Fallback gracioso se não disponível
    """
    try:
        from weasyprint import HTML
        from django.template.loader import render_to_string
        
        # Renderizar HTML
        html_string = render_to_string(template_name, context)
        
        # Converter para PDF
        pdf_bytes = HTML(string=html_string).write_pdf()
        
        # Preparar response
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename = context.get('pdf_filename', 'relatorio.pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        logger.info(
            f"PDF gerado com sucesso: {filename}. "
            f"Template: {template_name}, Tamanho: {len(pdf_bytes)} bytes"
        )
        
        return response
        
    except ImportError:
        logger.error(
            "WeasyPrint não está instalado. "
            "Execute: pip install weasyprint"
        )
        return HttpResponse(
            """
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #d32f2f;">WeasyPrint não instalado</h2>
                <p>Para gerar relatórios em PDF, instale o WeasyPrint:</p>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">pip install weasyprint</pre>
                <p><strong>Linux:</strong> Instale também as dependências do sistema:</p>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px;">sudo apt install libpango-1.0-0 libpangoft2-1.0-0</pre>
                <p><a href="javascript:history.back()" style="color: #1976d2;">← Voltar</a></p>
            </div>
            """,
            status=501,
            content_type='text/html',
        )
    
    except Exception as e:
        logger.error(
            f"Erro ao gerar PDF: {str(e)}. "
            f"Template: {template_name}",
            exc_info=True
        )
        return HttpResponse(
            f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #d32f2f;">Erro ao gerar PDF</h2>
                <p>Ocorreu um erro ao gerar o relatório em PDF:</p>
                <pre style="background: #f5f5f5; padding: 10px; border-radius: 4px; color: #d32f2f;">{str(e)}</pre>
                <p><a href="javascript:history.back()" style="color: #1976d2;">← Voltar</a></p>
            </div>
            """,
            status=500,
            content_type='text/html',
        )


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS HTML - RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_report_view(request):
    """
    Relatório por fazenda com filtros na mesma página.
    
    Filtros disponíveis:
    - farm (uuid): ID da fazenda (obrigatório para gerar relatório)
    - category (uuid): Categoria específica (opcional)
    - month (int): Mês do relatório (1-12)
    - year (int): Ano do relatório
    
    Returns:
        Template HTML com filtros e relatório (se farm selecionada)
    """
    try:
        # Dados para filtros
        farms = Farm.objects.filter(is_active=True).order_by('name')
        categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
        
        # Período
        today = date.today()
        months, years = _get_period_selects(today)
        start_date, end_date, month, year = _get_period_from_request(request)
        
        # Filtros selecionados
        farm_id = request.GET.get('farm', '').strip()
        category_id = request.GET.get('category', '').strip()
        
        # Gerar relatório se fazenda selecionada
        report = None
        if farm_id:
            try:
                # Validar que a fazenda existe e está ativa
                farm = get_object_or_404(Farm, pk=farm_id, is_active=True)
                
                # Gerar relatório
                report = FarmReportService.generate_report(
                    farm_id=farm_id,
                    start_date=start_date,
                    end_date=end_date,
                    animal_category_id=category_id if category_id else None
                )
                
                logger.info(
                    f"Relatório de fazenda gerado por {request.user.username}. "
                    f"Fazenda: {farm.name}, Período: {month}/{year}"
                )
                
            except Farm.DoesNotExist:
                messages.error(request, 'Fazenda não encontrada ou inativa.')
                farm_id = ''  # Reset selection
                
            except Exception as e:
                logger.error(
                    f"Erro ao gerar relatório de fazenda: {str(e)}. "
                    f"Fazenda: {farm_id}, Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    f'Erro ao gerar relatório. Por favor, tente novamente.'
                )
        
        context = {
            'farms': farms,
            'categories': categories,
            'report': report,
            'selected_farm_id': farm_id,
            'selected_category_id': category_id,
            'selected_month': month,
            'selected_year': year,
            'months': months,
            'years': years,
        }
        
        return render(request, 'reporting/farm_report.html', context)
        
    except Exception as e:
        logger.error(
            f"Erro na view de relatório por fazenda: {str(e)}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao carregar página de relatórios. Por favor, tente novamente.'
        )
        return render(request, 'reporting/farm_report.html', {
            'farms': [],
            'categories': [],
            'report': None,
        })


@login_required
@require_http_methods(["GET"])
def consolidated_report_view(request):
    """
    Relatório consolidado de todas as fazendas.
    
    Filtros disponíveis:
    - category (uuid): Categoria específica (opcional)
    - month (int): Mês do relatório (1-12)
    - year (int): Ano do relatório
    - gerar (flag): Trigger para gerar relatório
    
    Returns:
        Template HTML com filtros e relatório consolidado
    """
    try:
        # Dados para filtros
        categories = AnimalCategory.objects.filter(is_active=True).order_by('name')
        
        # Período
        today = date.today()
        months, years = _get_period_selects(today)
        start_date, end_date, month, year = _get_period_from_request(request)
        
        # Filtros selecionados
        category_id = request.GET.get('category', '').strip()
        gerar = request.GET.get('gerar')
        
        # Gerar relatório se solicitado
        report = None
        if gerar:
            try:
                report = ConsolidatedReportService.generate_consolidated_report(
                    start_date=start_date,
                    end_date=end_date,
                    animal_category_id=category_id if category_id else None
                )
                
                logger.info(
                    f"Relatório consolidado gerado por {request.user.username}. "
                    f"Período: {month}/{year}, "
                    f"Categoria: {category_id or 'Todas'}"
                )
                
            except Exception as e:
                logger.error(
                    f"Erro ao gerar relatório consolidado: {str(e)}. "
                    f"Usuário: {request.user.username}",
                    exc_info=True
                )
                messages.error(
                    request,
                    'Erro ao gerar relatório consolidado. Por favor, tente novamente.'
                )
        
        context = {
            'categories': categories,
            'report': report,
            'selected_category_id': category_id,
            'selected_month': month,
            'selected_year': year,
            'months': months,
            'years': years,
        }
        
        return render(request, 'reporting/consolidated_report.html', context)
        
    except Exception as e:
        logger.error(
            f"Erro na view de relatório consolidado: {str(e)}",
            exc_info=True
        )
        messages.error(
            request,
            'Erro ao carregar página de relatórios. Por favor, tente novamente.'
        )
        return render(request, 'reporting/consolidated_report.html', {
            'categories': [],
            'report': None,
        })


# ══════════════════════════════════════════════════════════════════════════════
# VIEWS PDF - EXPORTAÇÃO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def farm_report_pdf_view(request):
    """
    Exporta relatório de fazenda como PDF.
    
    Parâmetros obrigatórios:
    - farm (uuid): ID da fazenda
    
    Parâmetros opcionais:
    - category (uuid): Categoria específica
    - month (int): Mês do relatório
    - year (int): Ano do relatório
    
    Returns:
        PDF inline ou mensagem de erro
    """
    farm_id = request.GET.get('farm', '').strip()
    
    if not farm_id:
        logger.warning(
            f"Tentativa de gerar PDF sem farm_id. "
            f"Usuário: {request.user.username}"
        )
        raise Http404("Parâmetro 'farm' é obrigatório para gerar PDF.")
    
    try:
        # Validar fazenda
        farm = get_object_or_404(Farm, pk=farm_id, is_active=True)
        
        # Período e filtros
        category_id = request.GET.get('category', '').strip()
        start_date, end_date, month, year = _get_period_from_request(request)
        
        # Gerar relatório
        report = FarmReportService.generate_report(
            farm_id=farm_id,
            start_date=start_date,
            end_date=end_date,
            animal_category_id=category_id if category_id else None
        )
        
        # Nome do arquivo
        farm_slug = farm.name.lower().replace(' ', '-')
        filename = f"relatorio_{farm_slug}_{month:02d}-{year}.pdf"
        
        logger.info(
            f"PDF de relatório gerado por {request.user.username}. "
            f"Fazenda: {farm.name}, Arquivo: {filename}"
        )
        
        # Renderizar PDF
        return _render_pdf('reporting/farm_report_pdf.html', {
            'report': report,
            'user': request.user,
            'pdf_filename': filename,
        })
        
    except Farm.DoesNotExist:
        logger.error(f"Fazenda {farm_id} não encontrada para PDF")
        raise Http404("Fazenda não encontrada.")
        
    except Exception as e:
        logger.error(
            f"Erro ao gerar PDF de fazenda: {str(e)}. "
            f"Fazenda: {farm_id}, Usuário: {request.user.username}",
            exc_info=True
        )
        return HttpResponse(
            f"Erro ao gerar relatório em PDF. Por favor, tente novamente.",
            status=500
        )


@login_required
@require_http_methods(["GET"])
def consolidated_report_pdf_view(request):
    """
    Exporta relatório consolidado como PDF.
    
    Parâmetros opcionais:
    - category (uuid): Categoria específica
    - month (int): Mês do relatório
    - year (int): Ano do relatório
    
    Returns:
        PDF inline ou mensagem de erro
    """
    try:
        # Período e filtros
        category_id = request.GET.get('category', '').strip()
        start_date, end_date, month, year = _get_period_from_request(request)
        
        # Gerar relatório
        report = ConsolidatedReportService.generate_consolidated_report(
            start_date=start_date,
            end_date=end_date,
            animal_category_id=category_id if category_id else None
        )
        
        # Nome do arquivo
        filename = f"relatorio_consolidado_{month:02d}-{year}.pdf"
        
        logger.info(
            f"PDF de relatório consolidado gerado por {request.user.username}. "
            f"Período: {month}/{year}, Arquivo: {filename}"
        )
        
        # Renderizar PDF
        return _render_pdf('reporting/consolidated_report_pdf.html', {
            'report': report,
            'user': request.user,
            'pdf_filename': filename,
        })
        
    except Exception as e:
        logger.error(
            f"Erro ao gerar PDF consolidado: {str(e)}. "
            f"Usuário: {request.user.username}",
            exc_info=True
        )
        return HttpResponse(
            "Erro ao gerar relatório consolidado em PDF. Por favor, tente novamente.",
            status=500
        )


# ══════════════════════════════════════════════════════════════════════════════
# VIEW AUXILIAR - ÍNDICE DE RELATÓRIOS
# ══════════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(["GET"])
def report_index_view(request):
    """
    Página inicial de relatórios com cards de acesso rápido.
    
    Returns:
        Template com links para todos os relatórios disponíveis
    """
    context = {
        'total_farms': Farm.objects.filter(is_active=True).count(),
        'total_categories': AnimalCategory.objects.filter(is_active=True).count(),
    }
    
    logger.info(f"Índice de relatórios acessado por {request.user.username}")
    
    return render(request, 'reporting/report_index.html', context)
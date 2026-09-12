"""
finance/views/pdf.py

Geração de PDF do módulo financeiro, via WeasyPrint.

Os relatórios do sistema já usam WeasyPrint (`reporting/views.py::_render_pdf`),
e os PDFs do financeiro herdam o mesmo `pdf_base.html` para sair com a mesma
cara. A diferença desta função para aquela é a higienização do nome do
arquivo: `_render_pdf` interpola nomes de fazenda crus no cabeçalho HTTP, o
que quebra com acentos e parênteses — nomes reais como
"ROSS CLÉIA (SURP. NELSON)" existem no cadastro.
"""
import logging
import re
import unicodedata
from datetime import date

from django.http import HttpResponse
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def _slug_arquivo(texto):
    """
    Reduz um texto a algo seguro para o cabeçalho Content-Disposition:
    sem acentos, sem espaços e sem pontuação.
    """
    sem_acento = unicodedata.normalize('NFKD', str(texto))
    sem_acento = sem_acento.encode('ascii', 'ignore').decode('ascii')
    limpo = re.sub(r'[^A-Za-z0-9]+', '-', sem_acento).strip('-').lower()
    return limpo or 'relatorio'


def render_pdf(template_name, context, nome_arquivo='relatorio'):
    """
    Renderiza um template como PDF.

    Devolve uma resposta legível em caso de falha, em vez de deixar estourar
    um erro 500 — um PDF que não sai não pode derrubar a tela do usuário.
    """
    try:
        from weasyprint import HTML
    except ImportError:
        logger.error("WeasyPrint não está instalado — PDF indisponível.")
        return HttpResponse(
            "Geração de PDF indisponível: WeasyPrint não está instalado no servidor.",
            status=501,
        )

    try:
        contexto = dict(context)
        contexto.setdefault('gerado_em', date.today())

        html = render_to_string(template_name, contexto)
        pdf = HTML(string=html).write_pdf()

        arquivo = f"{_slug_arquivo(nome_arquivo)}-{date.today():%Y-%m-%d}.pdf"
        resposta = HttpResponse(pdf, content_type='application/pdf')
        resposta['Content-Disposition'] = f'inline; filename="{arquivo}"'
        return resposta

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Erro ao gerar PDF (%s): %s", template_name, exc, exc_info=True
        )
        return HttpResponse(
            "Não foi possível gerar o PDF. Tente novamente ou avise o suporte.",
            status=500,
        )

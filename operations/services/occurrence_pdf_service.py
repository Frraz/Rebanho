"""
operations/services/occurrence_pdf_service.py

Geração do PDF de histórico de ocorrências.
Design: minimalista, monocromático, tipografia limpa — estilo relatório corporativo.
"""

import io
import logging
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

logger = logging.getLogger(__name__)

# ── Paleta monocromática ──────────────────────────────────────────────────────
INK           = colors.HexColor('#111827')   # texto principal
INK_MED       = colors.HexColor('#374151')   # texto secundário
INK_LIGHT     = colors.HexColor('#9ca3af')   # texto terciário / cancelado
RULE          = colors.HexColor('#e5e7eb')   # linhas divisórias
ROW_SHADE     = colors.HexColor('#f9fafb')   # zebra suave
HEADER_BG     = colors.HexColor('#1f2937')   # cabeçalho de tabela — cinza muito escuro
HEADER_TEXT   = colors.white

OP_LABELS = {
    'MORTE':  'Morte',
    'ABATE':  'Abate',
    'VENDA':  'Venda',
    'DOACAO': 'Doação',
}


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE PÚBLICO
# ══════════════════════════════════════════════════════════════════════════════

class OccurrencePDFService:

    @staticmethod
    def generate(queryset, filters: dict, generated_by: str) -> bytes:
        movements = list(queryset.select_related(
            'farm_stock_balance__farm',
            'farm_stock_balance__animal_category',
            'client',
            'death_reason',
            'created_by',
        ).prefetch_related(
            'cancellation',
            'cancellation__cancelled_by',
        ))

        summary = OccurrencePDFService._build_summary(movements)
        buf = io.BytesIO()
        _Builder(buf, movements, filters, summary, generated_by).build()
        return buf.getvalue()

    @staticmethod
    def _build_summary(movements: list) -> dict:
        summary = {op: {'count': 0, 'qty': 0} for op in OP_LABELS}
        cancelled = 0
        for m in movements:
            if _Builder._is_cancelled(m):
                cancelled += 1
                continue
            op = m.operation_type
            if op in summary:
                summary[op]['count'] += 1
                summary[op]['qty'] += m.quantity
        summary['_cancelled'] = cancelled
        summary['_total_qty'] = sum(v['qty'] for k, v in summary.items() if not k.startswith('_'))
        summary['_total_count'] = sum(v['count'] for k, v in summary.items() if not k.startswith('_'))
        return summary


# ══════════════════════════════════════════════════════════════════════════════
# BUILDER INTERNO
# ══════════════════════════════════════════════════════════════════════════════

class _Builder:

    def __init__(self, buffer, movements, filters, summary, generated_by):
        self.buffer       = buffer
        self.movements    = movements
        self.filters      = filters
        self.summary      = summary
        self.generated_by = generated_by
        self.pw, self.ph  = landscape(A4)
        self.S            = self._styles()

    # ── Estilos ───────────────────────────────────────────────────────────────

    def _styles(self):
        base = getSampleStyleSheet()

        def ps(name, **kw):
            return ParagraphStyle(name, parent=base['Normal'], **kw)

        return {
            'doc_title': ps('DocTitle',
                fontSize=20, fontName='Helvetica-Bold',
                textColor=INK, spaceAfter=2, leading=24),

            'doc_meta': ps('DocMeta',
                fontSize=8, fontName='Helvetica',
                textColor=INK_LIGHT, spaceAfter=0, leading=12),

            'section': ps('Section',
                fontSize=7.5, fontName='Helvetica-Bold',
                textColor=INK_MED, spaceBefore=10, spaceAfter=4,
                leading=10),

            # Cabeçalho de coluna
            'th': ps('TH',
                fontSize=7.5, fontName='Helvetica-Bold',
                textColor=HEADER_TEXT, alignment=TA_LEFT, leading=10),

            'th_center': ps('THCenter',
                fontSize=7.5, fontName='Helvetica-Bold',
                textColor=HEADER_TEXT, alignment=TA_CENTER, leading=10),

            # Células normais
            'td': ps('TD',
                fontSize=7.5, fontName='Helvetica',
                textColor=INK, leading=10),

            'td_center': ps('TDCenter',
                fontSize=7.5, fontName='Helvetica',
                textColor=INK, alignment=TA_CENTER, leading=10),

            'td_right': ps('TDRight',
                fontSize=7.5, fontName='Helvetica',
                textColor=INK, alignment=TA_RIGHT, leading=10),

            # Células canceladas (esmaecidas)
            'td_dim': ps('TDDim',
                fontSize=7.5, fontName='Helvetica',
                textColor=INK_LIGHT, leading=10),

            'td_dim_center': ps('TDDimCenter',
                fontSize=7.5, fontName='Helvetica',
                textColor=INK_LIGHT, alignment=TA_CENTER, leading=10),

            # Kicker de resumo
            'kicker_val': ps('KickerVal',
                fontSize=16, fontName='Helvetica-Bold',
                textColor=INK, alignment=TA_CENTER, leading=20),

            'kicker_label': ps('KickerLabel',
                fontSize=7, fontName='Helvetica',
                textColor=INK_LIGHT, alignment=TA_CENTER, leading=9),
        }

    # ── Build principal ───────────────────────────────────────────────────────

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=landscape(A4),
            leftMargin=1.8 * cm,
            rightMargin=1.8 * cm,
            topMargin=2.2 * cm,
            bottomMargin=1.8 * cm,
            title='Histórico de Ocorrências',
            author='Sistema de Gestão de Rebanhos',
        )
        doc.build(
            self._story(),
            onFirstPage=self._page_frame,
            onLaterPages=self._page_frame,
        )

    # ── Frame de página (canvas direto) ──────────────────────────────────────

    def _page_frame(self, canvas, doc):
        canvas.saveState()
        w, h = self.pw, self.ph

        # Linha superior
        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.5)
        canvas.line(1.8 * cm, h - 1.0 * cm, w - 1.8 * cm, h - 1.0 * cm)

        # Nome do documento (topo esquerdo)
        canvas.setFillColor(INK)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(1.8 * cm, h - 0.75 * cm, 'HISTÓRICO DE OCORRÊNCIAS')

        # Data e usuário (topo direito)
        now_str = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(INK_LIGHT)
        canvas.drawRightString(
            w - 1.8 * cm, h - 0.75 * cm,
            f'{now_str}  ·  {self.generated_by}',
        )

        # Linha inferior
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, 1.2 * cm, w - 1.8 * cm, 1.2 * cm)

        # Paginação (rodapé)
        canvas.setFillColor(INK_LIGHT)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawRightString(w - 1.8 * cm, 0.7 * cm, f'Página {doc.page}')

        canvas.restoreState()

    # ── Story ─────────────────────────────────────────────────────────────────

    def _story(self):
        S = self.S
        story = []

        story.append(Spacer(1, 0.1 * cm))

        # Título + subtítulo com filtros
        story.append(Paragraph('Ocorrências', S['doc_title']))
        story.append(Paragraph(self._filters_text(), S['doc_meta']))
        story.append(Spacer(1, 0.5 * cm))

        story.append(HRFlowable(width='100%', thickness=0.5, color=RULE, spaceAfter=6))

        # Bloco de resumo
        story.append(self._summary_table())
        story.append(Spacer(1, 0.4 * cm))

        story.append(HRFlowable(width='100%', thickness=0.5, color=RULE, spaceAfter=6))

        # Tabela principal
        story.append(Paragraph('REGISTROS', S['section']))
        story.append(self._main_table())

        return story

    # ── Filtros ───────────────────────────────────────────────────────────────

    def _filters_text(self) -> str:
        f = self.filters
        MESES = {
            '1': 'Janeiro', '2': 'Fevereiro', '3': 'Março', '4': 'Abril',
            '5': 'Maio', '6': 'Junho', '7': 'Julho', '8': 'Agosto',
            '9': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro',
        }
        OPS = {'MORTE': 'Morte', 'ABATE': 'Abate', 'VENDA': 'Venda', 'DOACAO': 'Doação'}
        parts = []
        if f.get('search'):                        parts.append(f'Busca: "{f["search"]}"')
        if f.get('tipo') and f['tipo'] in OPS:     parts.append(f'Tipo: {OPS[f["tipo"]]}')
        if f.get('farm_name'):                     parts.append(f'Fazenda: {f["farm_name"]}')
        if f.get('mes') and f['mes'] in MESES:     parts.append(f'Mês: {MESES[f["mes"]]}')
        if f.get('ano'):                           parts.append(f'Ano: {f["ano"]}')
        return ('Filtros: ' + '  ·  '.join(parts)) if parts else 'Todos os registros'

    # ── Resumo (kickers) ──────────────────────────────────────────────────────

    def _summary_table(self) -> Table:
        s  = self.summary
        S  = self.S
        cw = (self.pw - 3.6 * cm) / 6

        def kicker(label, value):
            return [
                Paragraph(str(value), S['kicker_val']),
                Paragraph(label.upper(), S['kicker_label']),
            ]

        data = [[
            kicker('Mortes',        s['MORTE']['qty']),
            kicker('Abates',        s['ABATE']['qty']),
            kicker('Vendas',        s['VENDA']['qty']),
            kicker('Doações',       s['DOACAO']['qty']),
            kicker('Canceladas',    s['_cancelled']),
            kicker('Total animais', s['_total_qty']),
        ]]

        tbl = Table(data, colWidths=[cw] * 6)
        tbl.setStyle(TableStyle([
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            # Separadores verticais sutis entre kickers
            ('LINEAFTER',     (0, 0), (-2, -1), 0.5, RULE),
        ]))
        return tbl

    # ── Tabela principal ──────────────────────────────────────────────────────

    def _main_table(self) -> Table:
        S  = self.S
        cw = [
            2.5 * cm,   # Data
            4.2 * cm,   # Fazenda
            3.6 * cm,   # Categoria
            2.0 * cm,   # Tipo
            1.5 * cm,   # Qtd.
            6.2 * cm,   # Detalhes
            2.6 * cm,   # Usuário
            2.2 * cm,   # Status
        ]

        headers      = ['DATA', 'FAZENDA', 'CATEGORIA', 'TIPO', 'QTD.', 'DETALHES', 'USUÁRIO', 'STATUS']
        hdr_styles   = [S['th']] * 8
        hdr_styles[4] = S['th_center']
        hdr_styles[7] = S['th_center']

        data = [[Paragraph(h, hdr_styles[i]) for i, h in enumerate(headers)]]

        style_cmds = [
            ('BACKGROUND',    (0, 0), (-1, 0), HEADER_BG),
            ('TOPPADDING',    (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            # Apenas linhas horizontais no corpo — sem grid vertical
            ('LINEBELOW',     (0, 0), (-1, -1), 0.4, RULE),
            # Sem borda externa
            ('BOX',           (0, 0), (-1, -1), 0, colors.white),
        ]

        if not self.movements:
            data.append([Paragraph('Nenhum registro encontrado.', S['td_dim'])] + [''] * 7)
            style_cmds += [
                ('SPAN',  (0, 1), (-1, 1)),
                ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ]
        else:
            for i, m in enumerate(self.movements):
                row_n     = i + 1
                cancelled = self._is_cancelled(m)
                td        = S['td_dim']        if cancelled else S['td']
                td_c      = S['td_dim_center'] if cancelled else S['td_center']

                # Zebra discreta nas linhas pares
                if i % 2 == 1:
                    style_cmds.append(('BACKGROUND', (0, row_n), (-1, row_n), ROW_SHADE))

                row = [
                    Paragraph(
                        m.timestamp.strftime('%d/%m/%Y') +
                        f'<br/><font size="6.5" color="#9ca3af">{m.timestamp.strftime("%H:%M")}</font>',
                        td,
                    ),
                    Paragraph(m.farm_stock_balance.farm.name, td),
                    Paragraph(m.farm_stock_balance.animal_category.name, td),
                    Paragraph(
                        f'<font name="Helvetica-Bold">{OP_LABELS.get(m.operation_type, m.operation_type)}</font>',
                        td,
                    ),
                    Paragraph(f'<font name="Helvetica-Bold">-{m.quantity}</font>', td_c),
                    self._detail_cell(m, cancelled, td),
                    Paragraph(getattr(m.created_by, 'username', None) or 'Sistema', td),
                    Paragraph(
                        '<font color="#9ca3af">Cancelada</font>' if cancelled
                        else '<font name="Helvetica-Bold">Ativa</font>',
                        td_c,
                    ),
                ]
                data.append(row)

        tbl = Table(data, colWidths=cw, repeatRows=1)
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    # ── Célula de detalhes ────────────────────────────────────────────────────

    def _detail_cell(self, m, cancelled: bool, base_style) -> Paragraph:
        S = self.S
        if cancelled:
            try:
                c   = m.cancellation
                txt = (f'<i>Estornado em {c.cancelled_at.strftime("%d/%m/%Y %H:%M")} '
                       f'por {c.cancelled_by.username}</i>')
            except Exception:
                txt = '<i>Cancelada</i>'
            return Paragraph(txt, S['td_dim'])

        meta  = m.metadata or {}
        parts = []

        if m.client:
            parts.append(f'<b>{m.client.name}</b>')
            if meta.get('peso'):
                parts.append(f'{self._fmt(meta["peso"])} kg')
            if meta.get('preco_total'):
                parts.append(f'R$ {self._fmt(meta["preco_total"])}')
        elif m.death_reason:
            parts.append(m.death_reason.name)

        if meta.get('observacao'):
            obs = str(meta['observacao'])
            parts.append((obs[:57] + '…') if len(obs) > 60 else obs)

        return Paragraph('  ·  '.join(parts) if parts else '—', base_style)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_cancelled(m) -> bool:
        try:
            _ = m.cancellation
            return True
        except Exception:
            return False

    @staticmethod
    def _fmt(value) -> str:
        try:
            d = Decimal(str(value))
            return f'{d:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except (InvalidOperation, Exception):
            return str(value)
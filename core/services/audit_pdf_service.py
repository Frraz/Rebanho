"""
core/services/audit_pdf_service.py

Geração do PDF do Painel de Auditoria.
Design: minimalista, monocromático, tipografia limpa — mesmo estilo
corporativo de operations/services/occurrence_pdf_service.py.

Recebe os itens já enriquecidos por core/views_audit.py::_enrich (mesma
estrutura usada na listagem HTML), para não duplicar a lógica de detecção
de estorno/edição.
"""

import io
import logging

from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

logger = logging.getLogger(__name__)

# ── Paleta monocromática (igual à de operations/services/occurrence_pdf_service.py) ──
INK         = colors.HexColor('#111827')
INK_MED     = colors.HexColor('#374151')
INK_LIGHT   = colors.HexColor('#9ca3af')
RULE        = colors.HexColor('#e5e7eb')
ROW_SHADE   = colors.HexColor('#f9fafb')
HEADER_BG   = colors.HexColor('#1f2937')
HEADER_TEXT = colors.white


class AuditPDFService:

    @staticmethod
    def generate(items: list[dict], filters: dict, generated_by: str) -> bytes:
        summary = AuditPDFService._build_summary(items)
        buf = io.BytesIO()
        _Builder(buf, items, filters, summary, generated_by).build()
        return buf.getvalue()

    @staticmethod
    def _build_summary(items: list[dict]) -> dict:
        total = len(items)
        cancelled = sum(1 for it in items if it["cancellation"])
        edited = sum(1 for it in items if it["edited"] and not it["cancellation"])
        active = total - cancelled - edited
        entradas = sum(it["obj"].quantity for it in items if not it["is_saida"])
        saidas = sum(it["obj"].quantity for it in items if it["is_saida"])
        return {
            "total": total,
            "active": active,
            "edited": edited,
            "cancelled": cancelled,
            "entradas": entradas,
            "saidas": saidas,
        }


class _Builder:

    def __init__(self, buffer, items, filters, summary, generated_by):
        self.buffer = buffer
        self.items = items
        self.filters = filters
        self.summary = summary
        self.generated_by = generated_by
        self.pw, self.ph = landscape(A4)
        self.S = self._styles()

    def _styles(self):
        base = getSampleStyleSheet()

        def ps(name, **kw):
            return ParagraphStyle(name, parent=base['Normal'], **kw)

        return {
            'doc_title': ps('DocTitle', fontSize=20, fontName='Helvetica-Bold',
                             textColor=INK, spaceAfter=2, leading=24),
            'doc_meta': ps('DocMeta', fontSize=8, fontName='Helvetica',
                            textColor=INK_LIGHT, spaceAfter=0, leading=12),
            'section': ps('Section', fontSize=7.5, fontName='Helvetica-Bold',
                           textColor=INK_MED, spaceBefore=10, spaceAfter=4, leading=10),
            'th': ps('TH', fontSize=7.5, fontName='Helvetica-Bold',
                      textColor=HEADER_TEXT, alignment=TA_LEFT, leading=10),
            'th_center': ps('THCenter', fontSize=7.5, fontName='Helvetica-Bold',
                             textColor=HEADER_TEXT, alignment=TA_CENTER, leading=10),
            'td': ps('TD', fontSize=7.5, fontName='Helvetica', textColor=INK, leading=10),
            'td_center': ps('TDCenter', fontSize=7.5, fontName='Helvetica',
                             textColor=INK, alignment=TA_CENTER, leading=10),
            'td_dim': ps('TDDim', fontSize=7.5, fontName='Helvetica',
                          textColor=INK_LIGHT, leading=10),
            'td_dim_center': ps('TDDimCenter', fontSize=7.5, fontName='Helvetica',
                                 textColor=INK_LIGHT, alignment=TA_CENTER, leading=10),
            'kicker_val': ps('KickerVal', fontSize=16, fontName='Helvetica-Bold',
                              textColor=INK, alignment=TA_CENTER, leading=20),
            'kicker_label': ps('KickerLabel', fontSize=7, fontName='Helvetica',
                                textColor=INK_LIGHT, alignment=TA_CENTER, leading=9),
        }

    def build(self):
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=landscape(A4),
            leftMargin=1.8 * cm, rightMargin=1.8 * cm,
            topMargin=2.2 * cm, bottomMargin=1.8 * cm,
            title='Painel de Auditoria',
            author='Sistema de Gestão de Rebanhos',
        )
        doc.build(self._story(), onFirstPage=self._page_frame, onLaterPages=self._page_frame)

    def _page_frame(self, canvas, doc):
        canvas.saveState()
        w, h = self.pw, self.ph

        canvas.setStrokeColor(INK)
        canvas.setLineWidth(1.5)
        canvas.line(1.8 * cm, h - 1.0 * cm, w - 1.8 * cm, h - 1.0 * cm)

        canvas.setFillColor(INK)
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawString(1.8 * cm, h - 0.75 * cm, 'PAINEL DE AUDITORIA')

        now_str = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(INK_LIGHT)
        canvas.drawRightString(w - 1.8 * cm, h - 0.75 * cm, f'{now_str}  ·  {self.generated_by}')

        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(1.8 * cm, 1.2 * cm, w - 1.8 * cm, 1.2 * cm)

        canvas.setFillColor(INK_LIGHT)
        canvas.setFont('Helvetica', 7.5)
        canvas.drawRightString(w - 1.8 * cm, 0.7 * cm, f'Página {doc.page}')

        canvas.restoreState()

    def _story(self):
        S = self.S
        story = [Spacer(1, 0.1 * cm)]

        story.append(Paragraph('Auditoria', S['doc_title']))
        story.append(Paragraph(self._filters_text(), S['doc_meta']))
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=RULE, spaceAfter=6))

        story.append(self._summary_table())
        story.append(Spacer(1, 0.4 * cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=RULE, spaceAfter=6))

        story.append(Paragraph('REGISTROS', S['section']))
        story.append(self._main_table())

        return story

    def _filters_text(self) -> str:
        f = self.filters
        parts = []
        if f.get('search'):
            parts.append(f'Busca: "{f["search"]}"')
        if f.get('user_name'):
            parts.append(f'Usuário: {f["user_name"]}')
        if f.get('operation_label'):
            parts.append(f'Operação: {f["operation_label"]}')
        if f.get('farm_name'):
            parts.append(f'Fazenda: {f["farm_name"]}')
        if f.get('month_label'):
            parts.append(f'Mês: {f["month_label"]}')
        if f.get('year'):
            parts.append(f'Ano: {f["year"]}')
        if f.get('status_label'):
            parts.append(f'Status: {f["status_label"]}')
        return ('Filtros: ' + '  ·  '.join(parts)) if parts else 'Todos os registros'

    def _summary_table(self) -> Table:
        s = self.summary
        S = self.S
        cw = (self.pw - 3.6 * cm) / 6

        def kicker(label, value):
            return [Paragraph(str(value), S['kicker_val']), Paragraph(label.upper(), S['kicker_label'])]

        data = [[
            kicker('Total', s['total']),
            kicker('Ativas', s['active']),
            kicker('Editadas', s['edited']),
            kicker('Estornadas', s['cancelled']),
            kicker('Entradas', s['entradas']),
            kicker('Saídas', s['saidas']),
        ]]

        tbl = Table(data, colWidths=[cw] * 6)
        tbl.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LINEAFTER', (0, 0), (-2, -1), 0.5, RULE),
        ]))
        return tbl

    def _main_table(self) -> Table:
        S = self.S
        cw = [2.2 * cm, 3.4 * cm, 4.4 * cm, 3.6 * cm, 3.0 * cm, 1.6 * cm, 4.8 * cm]
        headers = ['DATA', 'USUÁRIO', 'FAZENDA', 'CATEGORIA', 'OPERAÇÃO', 'QTD.', 'STATUS']
        hdr_styles = [S['th']] * 7
        hdr_styles[5] = S['th_center']

        data = [[Paragraph(h, hdr_styles[i]) for i, h in enumerate(headers)]]

        style_cmds = [
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TOPPADDING', (0, 0), (-1, 0), 7),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
            ('LINEBELOW', (0, 0), (-1, -1), 0.4, RULE),
            ('BOX', (0, 0), (-1, -1), 0, colors.white),
        ]

        if not self.items:
            data.append([Paragraph('Nenhum registro encontrado.', S['td_dim'])] + [''] * 6)
            style_cmds += [('SPAN', (0, 1), (-1, 1)), ('ALIGN', (0, 1), (-1, 1), 'CENTER')]
        else:
            for i, item in enumerate(self.items):
                row_n = i + 1
                dim = bool(item["cancellation"])
                td = S['td_dim'] if dim else S['td']
                td_c = S['td_dim_center'] if dim else S['td_center']

                if i % 2 == 1:
                    style_cmds.append(('BACKGROUND', (0, row_n), (-1, row_n), ROW_SHADE))

                m = item["obj"]
                sinal = '-' if item["is_saida"] else '+'
                qty = f'<font name="Helvetica-Bold">{sinal}{m.quantity}</font>'

                row = [
                    Paragraph(m.timestamp.strftime('%d/%m/%Y'), td),
                    Paragraph(m.created_by.get_full_name() or m.created_by.username, td),
                    Paragraph(m.farm_stock_balance.farm.name, td),
                    Paragraph(m.farm_stock_balance.animal_category.name, td),
                    Paragraph(item["label"], td),
                    Paragraph(qty, td_c),
                    self._status_cell(item, td),
                ]
                data.append(row)

        tbl = Table(data, colWidths=cw, repeatRows=1)
        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    def _status_cell(self, item, base_style) -> Paragraph:
        S = self.S
        if item["cancellation"]:
            c = item["cancellation"]
            txt = f'<i>Estornada em {c.cancelled_at.strftime("%d/%m/%Y")} por {c.cancelled_by.username}</i>'
            return Paragraph(txt, S['td_dim'])
        if item["edited"]:
            who = f' por {item["history_user"].username}' if item["history_user"] else ''
            when = item["history_date"].strftime("%d/%m/%Y") if item["history_date"] else ''
            txt = f'<font name="Helvetica-Bold">Editada</font> {when}{who}'
            return Paragraph(txt, base_style)
        return Paragraph('Ativa', base_style)

"""
Consolidated Report Service - Relatórios Consolidados.

Responsável por gerar relatórios que consolidam múltiplas fazendas.
"""
from datetime import date
from typing import Dict, List, Any, Optional

from farms.models import Farm
from inventory.models import AnimalCategory
from reporting.services.farm_report_service import FarmReportService
from reporting.services.category_utils import sort_categories
from reporting.services.farm_utils import sort_farms, FARM_ORDER


# ── Helper para ordenar farm_reports (dataclass ou dict) ──────────────────────

_FARM_POSITIONS = {name: i for i, name in enumerate(FARM_ORDER)}


def _sort_farm_reports(reports):
    """
    Ordena lista de relatórios individuais na ordem canônica das fazendas.
    Aceita tanto dataclass (report.farm.name) quanto dict (report['farm'].name).
    """
    max_pos = len(_FARM_POSITIONS)

    def key(r):
        farm = r.farm if hasattr(r, 'farm') else r.get('farm')
        name = farm.name if hasattr(farm, 'name') else str(farm)
        return (_FARM_POSITIONS.get(name.strip().upper(), max_pos), name)

    return sorted(reports, key=key)


class ConsolidatedReportService:
    """
    Serviço de Relatórios Consolidados.

    Gera relatórios agregando dados de múltiplas fazendas.
    """

    @staticmethod
    def generate_consolidated_report(
        start_date: date,
        end_date: date,
        farm_ids: Optional[List[str]] = None,
        animal_category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Gera relatório consolidado de múltiplas fazendas.

        Args:
            start_date: Data inicial do período
            end_date: Data final do período
            farm_ids: Lista de IDs de fazendas (None = todas)
            animal_category_id: Categoria específica (opcional)

        Returns:
            Dicionário com dados consolidados
        """
        if farm_ids:
            farms = sort_farms(Farm.objects.filter(id__in=farm_ids, is_active=True))
        else:
            farms = sort_farms(Farm.objects.filter(is_active=True))

        # Gerar relatório individual de cada fazenda
        farm_reports = []
        for farm in farms:
            report = FarmReportService.generate_report(
                farm_id=str(farm.id),
                start_date=start_date,
                end_date=end_date,
                animal_category_id=animal_category_id
            )
            farm_reports.append(report)

        # Ordenar farm_reports na ordem canônica das fazendas
        farm_reports = _sort_farm_reports(farm_reports)

        # Consolidar dados
        consolidated_data = ConsolidatedReportService._consolidate_reports(
            farm_reports
        )

        return {
            'period': {
                'start': start_date,
                'end': end_date,
            },
            'farms': [farm.name for farm in farms],
            'farm_count': len(farms),
            'categories': consolidated_data['categories'],
            'estoque_inicial': consolidated_data['estoque_inicial'],
            'ocorrencias': consolidated_data['ocorrencias'],
            'entradas': consolidated_data['entradas'],
            'consolidado': consolidated_data['consolidado'],
            'detalhamento': consolidated_data['detalhamento'],
            'estoque_final': consolidated_data['estoque_final'],
            'farm_reports': farm_reports,
        }

    @staticmethod
    def _consolidate_reports(farm_reports: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Consolida múltiplos relatórios de fazendas em um único.

        Soma todos os valores por categoria.
        """
        consolidated = {
            'categories': set(),
            'estoque_inicial': {},
            'ocorrencias': {
                'morte': {},
                'venda': {},
                'abate': {},
                'doacao': {}
            },
            'entradas': {
                'nascimento': {},
                'desmame': {},
                'compra': {},
                'saldo': {},
                'manejo_in': {},
                'manejo_out': {},
                'mudanca_in': {},
                'mudanca_out': {}
            },
            'consolidado': {
                'entradas': {},
                'saidas': {}
            },
            'detalhamento': {
                'mortes': [],
                'vendas': [],
                'abates': [],
                'doacoes': []
            },
            'estoque_final': {}
        }

        for report in farm_reports:
            consolidated['categories'].update(report.categories)

            for category, qty in report.estoque_inicial.items():
                consolidated['estoque_inicial'][category] = \
                    consolidated['estoque_inicial'].get(category, 0) + qty

            for op_type in ['morte', 'venda', 'abate', 'doacao']:
                for category, qty in getattr(report.ocorrencias, op_type).items():
                    consolidated['ocorrencias'][op_type][category] = \
                        consolidated['ocorrencias'][op_type].get(category, 0) + qty

            for op_type in ['nascimento', 'desmame', 'compra', 'saldo',
                            'manejo_in', 'manejo_out', 'mudanca_in', 'mudanca_out']:
                for category, qty in getattr(report.entradas, op_type).items():
                    consolidated['entradas'][op_type][category] = \
                        consolidated['entradas'][op_type].get(category, 0) + qty

            for category, qty in report.consolidado.entradas.items():
                consolidated['consolidado']['entradas'][category] = \
                    consolidated['consolidado']['entradas'].get(category, 0) + qty

            for category, qty in report.consolidado.saidas.items():
                consolidated['consolidado']['saidas'][category] = \
                    consolidated['consolidado']['saidas'].get(category, 0) + qty

            consolidated['detalhamento']['mortes'].extend(report.detalhamento.mortes)
            consolidated['detalhamento']['vendas'].extend(report.detalhamento.vendas)
            consolidated['detalhamento']['abates'].extend(report.detalhamento.abates)
            consolidated['detalhamento']['doacoes'].extend(report.detalhamento.doacoes)

            for category, qty in report.estoque_final.items():
                consolidated['estoque_final'][category] = \
                    consolidated['estoque_final'].get(category, 0) + qty

        # Ordenação canônica das categorias
        consolidated['categories'] = sort_categories(
            list(consolidated['categories'])
        )

        # Ordenar detalhamentos por data (mais recente primeiro)
        for key in ['mortes', 'vendas', 'abates', 'doacoes']:
            consolidated['detalhamento'][key].sort(key=lambda x: x['data'], reverse=True)

        return consolidated
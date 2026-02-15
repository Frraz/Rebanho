"""
Consolidated Report Service - Relatórios Consolidados.

Responsável por gerar relatórios que consolidam múltiplas fazendas.
"""
from datetime import date
from typing import Dict, List, Any, Optional

from farms.models import Farm
from inventory.models import AnimalCategory
from reporting.services.farm_report_service import FarmReportService


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
        # Obter fazendas
        if farm_ids:
            farms = Farm.objects.filter(id__in=farm_ids, is_active=True)
        else:
            farms = Farm.objects.filter(is_active=True)
        
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
            'farm_reports': farm_reports,  # Relatórios individuais
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
        
        # Consolidar cada relatório
        for report in farm_reports:
            # Categorias
            consolidated['categories'].update(report['categories'])
            
            # Estoque inicial
            for category, qty in report['estoque_inicial'].items():
                consolidated['estoque_inicial'][category] = \
                    consolidated['estoque_inicial'].get(category, 0) + qty
            
            # Ocorrências
            for op_type in ['morte', 'venda', 'abate', 'doacao']:
                for category, qty in report['ocorrencias'][op_type].items():
                    consolidated['ocorrencias'][op_type][category] = \
                        consolidated['ocorrencias'][op_type].get(category, 0) + qty
            
            # Entradas
            for op_type in ['nascimento', 'desmame', 'compra', 'saldo', 
                           'manejo_in', 'manejo_out', 'mudanca_in', 'mudanca_out']:
                for category, qty in report['entradas'][op_type].items():
                    consolidated['entradas'][op_type][category] = \
                        consolidated['entradas'][op_type].get(category, 0) + qty
            
            # Consolidado
            for category, qty in report['consolidado']['entradas'].items():
                consolidated['consolidado']['entradas'][category] = \
                    consolidated['consolidado']['entradas'].get(category, 0) + qty
            
            for category, qty in report['consolidado']['saidas'].items():
                consolidated['consolidado']['saidas'][category] = \
                    consolidated['consolidado']['saidas'].get(category, 0) + qty
            
            # Detalhamento (concatenar listas)
            consolidated['detalhamento']['mortes'].extend(report['detalhamento']['mortes'])
            consolidated['detalhamento']['vendas'].extend(report['detalhamento']['vendas'])
            consolidated['detalhamento']['abates'].extend(report['detalhamento']['abates'])
            consolidated['detalhamento']['doacoes'].extend(report['detalhamento']['doacoes'])
            
            # Estoque final
            for category, qty in report['estoque_final'].items():
                consolidated['estoque_final'][category] = \
                    consolidated['estoque_final'].get(category, 0) + qty
        
        # Converter set de categorias para lista ordenada
        consolidated['categories'] = sorted(list(consolidated['categories']))
        
        # Ordenar detalhamentos por data
        for key in ['mortes', 'vendas', 'abates', 'doacoes']:
            consolidated['detalhamento'][key].sort(key=lambda x: x['data'], reverse=True)
        
        return consolidated
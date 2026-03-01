"""
Farm Report Service - Relatórios por Fazenda.

CORREÇÃO: Desmame exibe corretamente nas colunas do relatório:
  - DESMAME_OUT → coluna Desm. (negativo na categoria origem, ex: B. Macho)
  - DESMAME_IN  → coluna M.Cat.(+) (positivo na categoria destino, ex: Bois 2A.)

Lógica de negócio:
  O desmame é uma transferência entre categorias. A saída da categoria
  origem é um "desmame" (Desm.), mas a entrada na categoria destino é
  semanticamente uma "mudança de categoria" (M.Cat.+), não um desmame.
"""
from django.db.models import Sum
from django.utils import timezone
from datetime import datetime, date, time
from typing import Dict, List, Any, Optional

from inventory.models import AnimalMovement, AnimalCategory
from farms.models import Farm
from inventory.domain import OperationType
from inventory.domain.value_objects import MovementType


class FarmReportService:

    @staticmethod
    def generate_report(
        farm_id: str,
        start_date: date,
        end_date: date,
        animal_category_id: Optional[str] = None
    ) -> Dict[str, Any]:
        farm = Farm.objects.get(id=farm_id)

        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

        if animal_category_id:
            categories = list(AnimalCategory.objects.filter(id=animal_category_id))
        else:
            categories = list(AnimalCategory.objects.filter(is_active=True).order_by('name'))

        estoque_inicial = FarmReportService._calculate_initial_stock(
            farm_id, start_datetime, categories
        )
        movimentacoes = FarmReportService._get_period_movements(
            farm_id, start_datetime, end_datetime, categories
        )
        ocorrencias = FarmReportService._process_occurrences(movimentacoes, categories)
        entradas = FarmReportService._process_entries(movimentacoes, categories)
        detalhamento = FarmReportService._generate_details(movimentacoes)
        estoque_final = FarmReportService._calculate_final_stock(
            estoque_inicial, entradas, ocorrencias
        )
        consolidado = FarmReportService._generate_consolidated(entradas, ocorrencias)

        return {
            'farm': farm,
            'period': {'start': start_date, 'end': end_date},
            'categories': [cat.name for cat in categories],
            'estoque_inicial': estoque_inicial,
            'ocorrencias': ocorrencias,
            'entradas': entradas,
            'consolidado': consolidado,
            'detalhamento': detalhamento,
            'estoque_final': estoque_final,
        }

    @staticmethod
    def _calculate_initial_stock(
        farm_id: str,
        start_datetime: datetime,
        categories: List[AnimalCategory]
    ) -> Dict[str, int]:
        estoque = {}
        for category in categories:
            movements = AnimalMovement.objects.filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category=category,
                timestamp__lt=start_datetime
            )
            entradas = movements.filter(
                movement_type=MovementType.ENTRADA.value
            ).aggregate(total=Sum('quantity'))['total'] or 0

            saidas = movements.filter(
                movement_type=MovementType.SAIDA.value
            ).aggregate(total=Sum('quantity'))['total'] or 0

            estoque[category.name] = entradas - saidas
        return estoque

    @staticmethod
    def _get_period_movements(
        farm_id: str,
        start_datetime: datetime,
        end_datetime: datetime,
        categories: List[AnimalCategory]
    ) -> List[AnimalMovement]:
        return list(
            AnimalMovement.objects.filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category__in=categories,
                timestamp__gte=start_datetime,
                timestamp__lte=end_datetime,
            ).select_related(
                'farm_stock_balance__animal_category',
                'client',
                'death_reason',
                'created_by'
            ).order_by('timestamp')
        )

    @staticmethod
    def _process_occurrences(
        movements: List[AnimalMovement],
        categories: List[AnimalCategory]
    ) -> Dict[str, Any]:
        morte = {cat.name: 0 for cat in categories}
        venda = {cat.name: 0 for cat in categories}
        abate = {cat.name: 0 for cat in categories}
        doacao = {cat.name: 0 for cat in categories}

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name
            qty = m.quantity
            if m.operation_type == OperationType.MORTE.value:
                morte[cat] = morte.get(cat, 0) + qty
            elif m.operation_type == OperationType.VENDA.value:
                venda[cat] = venda.get(cat, 0) + qty
            elif m.operation_type == OperationType.ABATE.value:
                abate[cat] = abate.get(cat, 0) + qty
            elif m.operation_type == OperationType.DOACAO.value:
                doacao[cat] = doacao.get(cat, 0) + qty

        return {'morte': morte, 'venda': venda, 'abate': abate, 'doacao': doacao}

    @staticmethod
    def _process_entries(
        movements: List[AnimalMovement],
        categories: List[AnimalCategory]
    ) -> Dict[str, Any]:
        """
        Processa movimentos do período para exibição nas colunas do relatório.

        Mapeamento de operation_type → coluna do relatório:
          NASCIMENTO        → nascimento       (Nasc.)
          DESMAME_OUT       → desmame          (Desm.)   ← saída da categoria origem
          DESMAME_IN        → mudanca_in       (M.Cat.+) ← entrada na categoria destino
          COMPRA            → compra           (Compra)
          SALDO             → saldo            (interno)
          MANEJO_IN         → manejo_in        (Man.+)
          MANEJO_OUT        → manejo_out       (Man.-)
          MUDANCA_CATEGORIA_IN  → mudanca_in   (M.Cat.+)
          MUDANCA_CATEGORIA_OUT → mudanca_out  (M.Cat.-)

        CORREÇÃO: DESMAME_IN deixa de aparecer em Desm. e passa para M.Cat.(+),
        refletindo que a categoria destino recebeu animais por mudança de categoria,
        não por um evento de desmame propriamente dito.
        """
        zero = {cat.name: 0 for cat in categories}
        entries = {
            'nascimento': dict(zero),
            'desmame':    dict(zero),   # Apenas DESMAME_OUT (saída da origem)
            'compra':     dict(zero),
            'saldo':      dict(zero),
            'manejo_in':  dict(zero),
            'manejo_out': dict(zero),
            'mudanca_in': dict(zero),   # MUDANCA_CATEGORIA_IN + DESMAME_IN
            'mudanca_out': dict(zero),
        }

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name
            qty = m.quantity
            op = m.operation_type

            if op == OperationType.NASCIMENTO.value:
                entries['nascimento'][cat] = entries['nascimento'].get(cat, 0) + qty

            elif op == OperationType.DESMAME_OUT.value:
                # Saída da categoria origem → coluna Desm. (negativo)
                entries['desmame'][cat] = entries['desmame'].get(cat, 0) - qty

            elif op == OperationType.DESMAME_IN.value:
                # ✅ CORREÇÃO: entrada na categoria destino → coluna M.Cat.(+)
                # (antes aparecia em Desm. como positivo — incorreto)
                entries['mudanca_in'][cat] = entries['mudanca_in'].get(cat, 0) + qty

            elif op == OperationType.COMPRA.value:
                entries['compra'][cat] = entries['compra'].get(cat, 0) + qty

            elif op == OperationType.SALDO.value:
                entries['saldo'][cat] = entries['saldo'].get(cat, 0) + qty

            elif op == OperationType.MANEJO_IN.value:
                entries['manejo_in'][cat] = entries['manejo_in'].get(cat, 0) + qty

            elif op == OperationType.MANEJO_OUT.value:
                entries['manejo_out'][cat] = entries['manejo_out'].get(cat, 0) + qty

            elif op == OperationType.MUDANCA_CATEGORIA_IN.value:
                entries['mudanca_in'][cat] = entries['mudanca_in'].get(cat, 0) + qty

            elif op == OperationType.MUDANCA_CATEGORIA_OUT.value:
                entries['mudanca_out'][cat] = entries['mudanca_out'].get(cat, 0) + qty

        return entries

    @staticmethod
    def _generate_details(movements: List[AnimalMovement]) -> Dict[str, Any]:
        details = {'mortes': [], 'vendas': [], 'abates': [], 'doacoes': []}

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name
            if m.operation_type == OperationType.MORTE.value:
                details['mortes'].append({
                    'data': m.timestamp,
                    'categoria': cat,
                    'quantidade': m.quantity,
                    'motivo': m.death_reason.name if m.death_reason else '-',
                    'observacao': m.metadata.get('observacao', ''),
                })
            elif m.operation_type == OperationType.VENDA.value:
                details['vendas'].append({
                    'data': m.timestamp,
                    'categoria': cat,
                    'quantidade': m.quantity,
                    'cliente': m.client.name if m.client else '-',
                    'peso': m.metadata.get('peso', '-'),
                    'preco': m.metadata.get('preco_total', '-'),
                })
            elif m.operation_type == OperationType.ABATE.value:
                details['abates'].append({
                    'data': m.timestamp,
                    'categoria': cat,
                    'quantidade': m.quantity,
                    'peso': m.metadata.get('peso', '-'),
                    'observacao': m.metadata.get('observacao', ''),
                })
            elif m.operation_type == OperationType.DOACAO.value:
                details['doacoes'].append({
                    'data': m.timestamp,
                    'categoria': cat,
                    'quantidade': m.quantity,
                    'cliente': m.client.name if m.client else '-',
                    'peso': m.metadata.get('peso', '-'),
                    'observacao': m.metadata.get('observacao', ''),
                })
        return details

    @staticmethod
    def _calculate_final_stock(
        estoque_inicial: Dict[str, int],
        entradas: Dict[str, Any],
        ocorrencias: Dict[str, Any]
    ) -> Dict[str, int]:
        """
        Calcula estoque final.

        Nota: entradas['desmame'] já carrega valor negativo (DESMAME_OUT),
        então é somado (não subtraído) para decrementar corretamente.
        entradas['mudanca_in'] inclui DESMAME_IN + MUDANCA_CATEGORIA_IN.
        """
        estoque_final = {}
        for category, qty_inicial in estoque_inicial.items():
            total_entradas = (
                entradas['nascimento'].get(category, 0) +
                entradas['compra'].get(category, 0) +
                entradas['saldo'].get(category, 0) +
                entradas['manejo_in'].get(category, 0) +
                entradas['mudanca_in'].get(category, 0)
                # desmame NÃO entra aqui — já é negativo e vai em total_saidas
            )
            total_saidas = (
                ocorrencias['morte'].get(category, 0) +
                ocorrencias['venda'].get(category, 0) +
                ocorrencias['abate'].get(category, 0) +
                ocorrencias['doacao'].get(category, 0) +
                entradas['manejo_out'].get(category, 0) +
                entradas['mudanca_out'].get(category, 0) +
                abs(entradas['desmame'].get(category, 0))  # DESMAME_OUT (valor negativo → abs)
            )
            estoque_final[category] = qty_inicial + total_entradas - total_saidas
        return estoque_final

    @staticmethod
    def _generate_consolidated(
        entradas: Dict[str, Any],
        ocorrencias: Dict[str, Any]
    ) -> Dict[str, Dict[str, int]]:
        """
        Gera totais consolidados de Entrada e Saída por categoria.

        Entradas consolidadas: nascimento + compra + saldo + manejo_in + mudanca_in
          (mudanca_in já inclui DESMAME_IN)
        Saídas consolidadas:   morte + venda + abate + doação + manejo_out + mudanca_out + |desmame|
          (desmame = DESMAME_OUT, valor negativo → usa abs())
        """
        consolidado_entradas = {}
        consolidado_saidas = {}

        # Entradas: tudo exceto desmame (que é saída)
        for op in ['nascimento', 'compra', 'saldo', 'manejo_in', 'mudanca_in']:
            for cat, qty in entradas[op].items():
                if qty:
                    consolidado_entradas[cat] = consolidado_entradas.get(cat, 0) + qty

        # Saídas: ocorrências
        for op in ['morte', 'venda', 'abate', 'doacao']:
            for cat, qty in ocorrencias[op].items():
                if qty:
                    consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty

        # Saídas: manejo_out e mudanca_out
        for cat, qty in entradas['manejo_out'].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty
        for cat, qty in entradas['mudanca_out'].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty

        # Saídas: desmame (DESMAME_OUT está como valor negativo → abs)
        for cat, qty in entradas['desmame'].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + abs(qty)

        return {'entradas': consolidado_entradas, 'saidas': consolidado_saidas}
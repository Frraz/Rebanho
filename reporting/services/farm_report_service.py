"""
Farm Report Service - Relatórios por Fazenda.

REGRAS IMPORTANTES DE CONSISTÊNCIA:
1) Movimentos CANCELADOS não entram em cálculos de relatório
   (filtramos cancellation__isnull=True).
2) DESMAME é tratado como transferência entre categorias:
   - DESMAME_OUT -> coluna "desmame" (saída da categoria origem)
   - DESMAME_IN  -> coluna "mudanca_in" (entrada na categoria destino)
3) Relatório é baseado no LEDGER ativo (não cancelado), mantendo
   coerência com os saldos atuais exibidos no sistema.
"""

from datetime import datetime, date, time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

from django.db.models import Sum
from django.utils import timezone

from farms.models import Farm
from inventory.models import AnimalMovement, AnimalCategory
from inventory.domain import OperationType
from inventory.domain.value_objects import MovementType
from reporting.services.category_utils import sort_categories


# ══════════════════════════════════════════════════════════════════════════════
# VALUE OBJECTS - permitem acesso por atributo nos templates Django
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReportPeriod:
    start: date
    end: date


@dataclass
class ReportOcorrencias:
    morte: Dict[str, int]
    venda: Dict[str, int]
    abate: Dict[str, int]
    doacao: Dict[str, int]


@dataclass
class ReportEntradas:
    nascimento: Dict[str, int]
    desmame: Dict[str, int]
    compra: Dict[str, int]
    saldo: Dict[str, int]
    manejo_in: Dict[str, int]
    manejo_out: Dict[str, int]
    mudanca_in: Dict[str, int]
    mudanca_out: Dict[str, int]


@dataclass
class ReportConsolidado:
    entradas: Dict[str, int]
    saidas: Dict[str, int]


@dataclass
class ReportDetalhamento:
    mortes: List[Dict[str, Any]] = field(default_factory=list)
    vendas: List[Dict[str, Any]] = field(default_factory=list)
    abates: List[Dict[str, Any]] = field(default_factory=list)
    doacoes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class FarmReport:
    farm: Any                          # Farm ORM object
    period: ReportPeriod
    categories: List[str]
    estoque_inicial: Dict[str, int]
    estoque_final: Dict[str, int]
    ocorrencias: ReportOcorrencias
    entradas: ReportEntradas
    consolidado: ReportConsolidado
    detalhamento: ReportDetalhamento


# ══════════════════════════════════════════════════════════════════════════════
# SERVICE
# ══════════════════════════════════════════════════════════════════════════════

class FarmReportService:

    @staticmethod
    def generate(
        farm: Farm,
        start_date: date,
        end_date: date,
        category: Optional[AnimalCategory] = None,
    ) -> FarmReport:
        """
        Interface principal usada pelas views.
        Recebe objetos ORM diretamente e retorna um FarmReport acessível
        por atributos nos templates Django (report.period.start, etc.).
        """
        return FarmReportService.generate_report(
            farm_id=str(farm.id),
            start_date=start_date,
            end_date=end_date,
            animal_category_id=str(category.id) if category else None,
        )

    @staticmethod
    def generate_report(
        farm_id: str,
        start_date: date,
        end_date: date,
        animal_category_id: Optional[str] = None,
    ) -> FarmReport:
        """
        Gera o relatório completo por fazenda.
        Retorna um FarmReport (dataclass) em vez de dict puro,
        garantindo acesso por atributo nos templates.
        """
        farm = Farm.objects.get(id=farm_id)

        start_datetime = timezone.make_aware(datetime.combine(start_date, time.min))
        end_datetime = timezone.make_aware(datetime.combine(end_date, time.max))

        if animal_category_id:
            categories = list(AnimalCategory.objects.filter(id=animal_category_id))
        else:
            # Ordenação canônica zootécnica definida em category_utils.py.
            # Não usar order_by('name') — a ordem é controlada por sort_categories().
            categories = sort_categories(
                list(AnimalCategory.objects.filter(is_active=True))
            )

        estoque_inicial = FarmReportService._calculate_initial_stock(
            farm_id, start_datetime, categories
        )
        movimentacoes = FarmReportService._get_period_movements(
            farm_id, start_datetime, end_datetime, categories
        )
        ocorrencias_dict = FarmReportService._process_occurrences(movimentacoes, categories)
        entradas_dict = FarmReportService._process_entries(movimentacoes, categories)
        detalhamento_dict = FarmReportService._generate_details(movimentacoes)
        estoque_final = FarmReportService._calculate_final_stock(
            estoque_inicial, entradas_dict, ocorrencias_dict
        )
        consolidado_dict = FarmReportService._generate_consolidated(entradas_dict, ocorrencias_dict)

        return FarmReport(
            farm=farm,
            period=ReportPeriod(start=start_date, end=end_date),
            categories=[cat.name for cat in categories],
            estoque_inicial=estoque_inicial,
            estoque_final=estoque_final,
            ocorrencias=ReportOcorrencias(
                morte=ocorrencias_dict["morte"],
                venda=ocorrencias_dict["venda"],
                abate=ocorrencias_dict["abate"],
                doacao=ocorrencias_dict["doacao"],
            ),
            entradas=ReportEntradas(
                nascimento=entradas_dict["nascimento"],
                desmame=entradas_dict["desmame"],
                compra=entradas_dict["compra"],
                saldo=entradas_dict["saldo"],
                manejo_in=entradas_dict["manejo_in"],
                manejo_out=entradas_dict["manejo_out"],
                mudanca_in=entradas_dict["mudanca_in"],
                mudanca_out=entradas_dict["mudanca_out"],
            ),
            consolidado=ReportConsolidado(
                entradas=consolidado_dict["entradas"],
                saidas=consolidado_dict["saidas"],
            ),
            detalhamento=ReportDetalhamento(
                mortes=detalhamento_dict["mortes"],
                vendas=detalhamento_dict["vendas"],
                abates=detalhamento_dict["abates"],
                doacoes=detalhamento_dict["doacoes"],
            ),
        )

    @staticmethod
    def _calculate_initial_stock(
        farm_id: str,
        start_datetime: datetime,
        categories: List[AnimalCategory],
    ) -> Dict[str, int]:
        """
        Calcula estoque anterior ao período.

        CRÍTICO: ignora movimentos cancelados para não inflar/sujar o histórico.
        """
        estoque: Dict[str, int] = {}

        for category in categories:
            movements = AnimalMovement.objects.filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category=category,
                timestamp__lt=start_datetime,
                cancellation__isnull=True,
            )

            entradas = (
                movements.filter(movement_type=MovementType.ENTRADA.value)
                .aggregate(total=Sum("quantity"))
                .get("total")
                or 0
            )
            saidas = (
                movements.filter(movement_type=MovementType.SAIDA.value)
                .aggregate(total=Sum("quantity"))
                .get("total")
                or 0
            )

            estoque[category.name] = entradas - saidas

        return estoque

    @staticmethod
    def _get_period_movements(
        farm_id: str,
        start_datetime: datetime,
        end_datetime: datetime,
        categories: List[AnimalCategory],
    ) -> List[AnimalMovement]:
        """
        Busca movimentos do período.

        CRÍTICO: apenas movimentos ativos (não cancelados).
        """
        return list(
            AnimalMovement.objects.filter(
                farm_stock_balance__farm_id=farm_id,
                farm_stock_balance__animal_category__in=categories,
                timestamp__gte=start_datetime,
                timestamp__lte=end_datetime,
                cancellation__isnull=True,
            )
            .select_related(
                "farm_stock_balance__animal_category",
                "client",
                "death_reason",
                "created_by",
            )
            .order_by("timestamp")
        )

    @staticmethod
    def _process_occurrences(
        movements: List[AnimalMovement],
        categories: List[AnimalCategory],
    ) -> Dict[str, Any]:
        morte  = {cat.name: 0 for cat in categories}
        venda  = {cat.name: 0 for cat in categories}
        abate  = {cat.name: 0 for cat in categories}
        doacao = {cat.name: 0 for cat in categories}

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name
            qty = m.quantity

            if m.operation_type == OperationType.MORTE.value:
                morte[cat]  = morte.get(cat, 0)  + qty
            elif m.operation_type == OperationType.VENDA.value:
                venda[cat]  = venda.get(cat, 0)  + qty
            elif m.operation_type == OperationType.ABATE.value:
                abate[cat]  = abate.get(cat, 0)  + qty
            elif m.operation_type == OperationType.DOACAO.value:
                doacao[cat] = doacao.get(cat, 0) + qty

        return {"morte": morte, "venda": venda, "abate": abate, "doacao": doacao}

    @staticmethod
    def _process_entries(
        movements: List[AnimalMovement],
        categories: List[AnimalCategory],
    ) -> Dict[str, Any]:
        """
        Mapeamento de operation_type -> colunas do relatório:
          NASCIMENTO             -> nascimento
          DESMAME_OUT            -> desmame (negativo na origem)
          DESMAME_IN             -> mudanca_in (positivo no destino)
          COMPRA                 -> compra
          SALDO                  -> saldo
          MANEJO_IN              -> manejo_in
          MANEJO_OUT             -> manejo_out
          MUDANCA_CATEGORIA_IN   -> mudanca_in
          MUDANCA_CATEGORIA_OUT  -> mudanca_out
        """
        zero = {cat.name: 0 for cat in categories}
        entries = {
            "nascimento": dict(zero),
            "desmame":    dict(zero),
            "compra":     dict(zero),
            "saldo":      dict(zero),
            "manejo_in":  dict(zero),
            "manejo_out": dict(zero),
            "mudanca_in": dict(zero),
            "mudanca_out": dict(zero),
        }

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name
            qty = m.quantity
            op  = m.operation_type

            if op == OperationType.NASCIMENTO.value:
                entries["nascimento"][cat] += qty
            elif op == OperationType.DESMAME_OUT.value:
                entries["desmame"][cat] -= qty          # negativo intencional
            elif op == OperationType.DESMAME_IN.value:
                entries["mudanca_in"][cat] += qty
            elif op == OperationType.COMPRA.value:
                entries["compra"][cat] += qty
            elif op == OperationType.SALDO.value:
                entries["saldo"][cat] += qty
            elif op == OperationType.MANEJO_IN.value:
                entries["manejo_in"][cat] += qty
            elif op == OperationType.MANEJO_OUT.value:
                entries["manejo_out"][cat] += qty
            elif op == OperationType.MUDANCA_CATEGORIA_IN.value:
                entries["mudanca_in"][cat] += qty
            elif op == OperationType.MUDANCA_CATEGORIA_OUT.value:
                entries["mudanca_out"][cat] += qty

        return entries

    @staticmethod
    def _generate_details(movements: List[AnimalMovement]) -> Dict[str, Any]:
        details: Dict[str, List] = {
            "mortes": [], "vendas": [], "abates": [], "doacoes": []
        }

        for m in movements:
            cat = m.farm_stock_balance.animal_category.name

            if m.operation_type == OperationType.MORTE.value:
                details["mortes"].append({
                    "data":       m.timestamp,
                    "categoria":  cat,
                    "quantidade": m.quantity,
                    "motivo":     m.death_reason.name if m.death_reason else "-",
                    "observacao": m.metadata.get("observacao", ""),
                })
            elif m.operation_type == OperationType.VENDA.value:
                details["vendas"].append({
                    "data":       m.timestamp,
                    "categoria":  cat,
                    "quantidade": m.quantity,
                    "cliente":    m.client.name if m.client else "-",
                    "peso":       m.metadata.get("peso", "-"),
                    "preco":      m.metadata.get("preco_total", "-"),
                })
            elif m.operation_type == OperationType.ABATE.value:
                details["abates"].append({
                    "data":       m.timestamp,
                    "categoria":  cat,
                    "quantidade": m.quantity,
                    "peso":       m.metadata.get("peso", "-"),
                    "observacao": m.metadata.get("observacao", ""),
                })
            elif m.operation_type == OperationType.DOACAO.value:
                details["doacoes"].append({
                    "data":       m.timestamp,
                    "categoria":  cat,
                    "quantidade": m.quantity,
                    "cliente":    m.client.name if m.client else "-",
                    "peso":       m.metadata.get("peso", "-"),
                    "observacao": m.metadata.get("observacao", ""),
                })

        return details

    @staticmethod
    def _calculate_final_stock(
        estoque_inicial: Dict[str, int],
        entradas: Dict[str, Any],
        ocorrencias: Dict[str, Any],
    ) -> Dict[str, int]:
        """
        Calcula estoque final por categoria.

        Nota: desmame (DESMAME_OUT) está negativo em entradas['desmame'],
        por isso é somado via abs() no bloco de saídas.
        """
        estoque_final: Dict[str, int] = {}

        for category, qty_inicial in estoque_inicial.items():
            total_entradas = (
                entradas["nascimento"].get(category, 0)
                + entradas["compra"].get(category, 0)
                + entradas["saldo"].get(category, 0)
                + entradas["manejo_in"].get(category, 0)
                + entradas["mudanca_in"].get(category, 0)
            )
            total_saidas = (
                ocorrencias["morte"].get(category, 0)
                + ocorrencias["venda"].get(category, 0)
                + ocorrencias["abate"].get(category, 0)
                + ocorrencias["doacao"].get(category, 0)
                + entradas["manejo_out"].get(category, 0)
                + entradas["mudanca_out"].get(category, 0)
                + abs(entradas["desmame"].get(category, 0))
            )
            estoque_final[category] = qty_inicial + total_entradas - total_saidas

        return estoque_final

    @staticmethod
    def _generate_consolidated(
        entradas: Dict[str, Any],
        ocorrencias: Dict[str, Any],
    ) -> Dict[str, Dict[str, int]]:
        """
        Gera consolidados por categoria:
        - entradas: nascimento, compra, saldo, manejo_in, mudanca_in
        - saídas:   morte, venda, abate, doacao, manejo_out, mudanca_out, abs(desmame)
        """
        consolidado_entradas: Dict[str, int] = {}
        consolidado_saidas: Dict[str, int]   = {}

        for op in ["nascimento", "compra", "saldo", "manejo_in", "mudanca_in"]:
            for cat, qty in entradas[op].items():
                if qty:
                    consolidado_entradas[cat] = consolidado_entradas.get(cat, 0) + qty

        for op in ["morte", "venda", "abate", "doacao"]:
            for cat, qty in ocorrencias[op].items():
                if qty:
                    consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty

        for cat, qty in entradas["manejo_out"].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty

        for cat, qty in entradas["mudanca_out"].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + qty

        for cat, qty in entradas["desmame"].items():
            if qty:
                consolidado_saidas[cat] = consolidado_saidas.get(cat, 0) + abs(qty)

        return {"entradas": consolidado_entradas, "saidas": consolidado_saidas}
"""
Transfer Service - Serviço de Transferências.

Responsável por operações COMPOSTAS que envolvem múltiplas movimentações:
- MANEJO: Transferência entre fazendas (saída + entrada)
- MUDANÇA DE CATEGORIA: Alteração de categoria (saída + entrada)
- DESMAME: Mudança automática de categorias pré-definidas (saída + entrada × N)

IMPORTANTE: Estas operações são ATÔMICAS - se uma parte falha, tudo é revertido.
"""
from django.db import transaction
from django.utils import timezone
from typing import Optional, Dict, Any, Tuple, List

from inventory.models import AnimalMovement, AnimalCategory
from inventory.domain import (
    OperationType,
    validate_positive_quantity,
    validate_manejo_parameters,
    validate_category_change_parameters,
    validate_weaning_parameters,
    WeaningCategoryNotFoundError,
)
from inventory.services.movement_service import MovementService


class TransferService:
    """
    Serviço de Transferências (Operações Compostas).

    Garante que operações complexas sejam executadas atomicamente.
    """

    @staticmethod
    @transaction.atomic
    def execute_manejo(
        source_farm_id: str,
        target_farm_id: str,
        animal_category_id: str,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[AnimalMovement, AnimalMovement]:
        """
        Executa MANEJO: Transferência de animais entre fazendas.

        Esta é uma operação COMPOSTA que realiza:
        1. SAÍDA da fazenda origem (MANEJO_OUT)
        2. ENTRADA na fazenda destino (MANEJO_IN)

        A operação é ATÔMICA: se qualquer parte falhar, tudo é revertido.
        """

        # 1. VALIDAÇÕES DE DOMÍNIO
        validate_positive_quantity(quantity)
        validate_manejo_parameters(source_farm_id, target_farm_id)

        operation_timestamp = timestamp or timezone.now()
        operation_metadata = metadata or {}

        saida_metadata = {
            **operation_metadata,
            'fazenda_destino': str(target_farm_id),
            'tipo_transferencia': 'manejo'
        }

        entrada_metadata = {
            **operation_metadata,
            'fazenda_origem': str(source_farm_id),
            'tipo_transferencia': 'manejo'
        }

        # 2. EXECUTAR SAÍDA DA FAZENDA ORIGEM
        movimento_saida = MovementService.execute_saida(
            farm_id=source_farm_id,
            animal_category_id=animal_category_id,
            operation_type=OperationType.MANEJO_OUT,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=saida_metadata,
            ip_address=ip_address,
        )

        # 3. EXECUTAR ENTRADA NA FAZENDA DESTINO
        movimento_entrada = MovementService.execute_entrada(
            farm_id=target_farm_id,
            animal_category_id=animal_category_id,
            operation_type=OperationType.MANEJO_IN,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=entrada_metadata,
            ip_address=ip_address,
        )

        return (movimento_saida, movimento_entrada)

    @staticmethod
    @transaction.atomic
    def execute_mudanca_categoria(
        farm_id: str,
        source_category_id: str,
        target_category_id: str,
        quantity: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[AnimalMovement, AnimalMovement]:
        """
        Executa MUDANÇA DE CATEGORIA: Altera categoria de animais.

        Esta é uma operação COMPOSTA que realiza:
        1. SAÍDA da categoria origem (MUDANCA_CATEGORIA_OUT)
        2. ENTRADA na categoria destino (MUDANCA_CATEGORIA_IN)

        A operação é ATÔMICA: se qualquer parte falhar, tudo é revertido.
        """

        # 1. VALIDAÇÕES DE DOMÍNIO
        validate_positive_quantity(quantity)
        validate_category_change_parameters(source_category_id, target_category_id)

        operation_timestamp = timestamp or timezone.now()
        operation_metadata = metadata or {}

        saida_metadata = {
            **operation_metadata,
            'categoria_destino': str(target_category_id),
            'tipo_transferencia': 'mudanca_categoria'
        }

        entrada_metadata = {
            **operation_metadata,
            'categoria_origem': str(source_category_id),
            'tipo_transferencia': 'mudanca_categoria'
        }

        # 2. EXECUTAR SAÍDA DA CATEGORIA ORIGEM
        movimento_saida = MovementService.execute_saida(
            farm_id=farm_id,
            animal_category_id=source_category_id,
            operation_type=OperationType.MUDANCA_CATEGORIA_OUT,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=saida_metadata,
            ip_address=ip_address,
        )

        # 3. EXECUTAR ENTRADA NA CATEGORIA DESTINO
        movimento_entrada = MovementService.execute_entrada(
            farm_id=farm_id,
            animal_category_id=target_category_id,
            operation_type=OperationType.MUDANCA_CATEGORIA_IN,
            quantity=quantity,
            user=user,
            timestamp=operation_timestamp,
            metadata=entrada_metadata,
            ip_address=ip_address,
        )

        return (movimento_saida, movimento_entrada)

    # ══════════════════════════════════════════════════════════════════════
    # DESMAME — Operação composta com regras automáticas
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    @transaction.atomic
    def execute_desmame(
        farm_id: str,
        quantity_males: int,
        quantity_females: int,
        user,
        timestamp: Optional[timezone.datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> List[Tuple[AnimalMovement, AnimalMovement]]:
        """
        Executa DESMAME: Mudança automática de categorias pré-definidas.

        O desmame é uma operação composta que segue regras FIXAS:
            B. Macho  → Bois - 2A.   (se quantity_males > 0)
            B. Fêmea  → Nov. - 2A.   (se quantity_females > 0)

        Para cada par origem→destino com quantidade > 0:
        1. SAÍDA da categoria origem (DESMAME_OUT)
        2. ENTRADA na categoria destino (DESMAME_IN)

        A operação é TOTALMENTE ATÔMICA:
        - Se o desmame de machos funciona mas o de fêmeas falha,
          TUDO é revertido (inclusive os machos).

        Args:
            farm_id: UUID da fazenda
            quantity_males: Qtd de B. Macho a desmamar (0 para pular)
            quantity_females: Qtd de B. Fêmea a desmamar (0 para pular)
            user: Usuário que está registrando a operação
            timestamp: Data/hora da operação (default: agora)
            metadata: Dados adicionais em JSON
            ip_address: IP de origem da requisição

        Returns:
            List[Tuple[AnimalMovement, AnimalMovement]]:
                Lista de pares (saída, entrada) para cada categoria desmamada.

        Raises:
            InvalidOperationError: Se ambas quantidades forem 0
            InsufficientStockError: Se saldo insuficiente
            WeaningCategoryNotFoundError: Se categorias do sistema não existirem
        """

        # 1. VALIDAÇÃO DE PARÂMETROS
        validate_weaning_parameters(farm_id, quantity_males, quantity_females)

        operation_timestamp = timestamp or timezone.now()
        base_metadata = metadata or {}

        # 2. CARREGAR CATEGORIAS DO SISTEMA (por slug — seguro)
        weaning_rules = AnimalCategory.WeaningRules
        required_slugs = set()

        if quantity_males > 0:
            required_slugs.add(AnimalCategory.SystemSlugs.BEZERRO_MACHO)
            required_slugs.add(AnimalCategory.SystemSlugs.BOIS_2A)

        if quantity_females > 0:
            required_slugs.add(AnimalCategory.SystemSlugs.BEZERRO_FEMEA)
            required_slugs.add(AnimalCategory.SystemSlugs.NOVILHA_2A)

        categories = {
            cat.slug: cat
            for cat in AnimalCategory.objects.filter(slug__in=required_slugs)
        }

        # Validar que TODAS as categorias necessárias existem
        for slug in required_slugs:
            if slug not in categories:
                raise WeaningCategoryNotFoundError(slug)

        # 3. MONTAR OPERAÇÕES A EXECUTAR
        operations = []

        if quantity_males > 0:
            operations.append({
                'source': categories[AnimalCategory.SystemSlugs.BEZERRO_MACHO],
                'target': categories[AnimalCategory.SystemSlugs.BOIS_2A],
                'quantity': quantity_males,
            })

        if quantity_females > 0:
            operations.append({
                'source': categories[AnimalCategory.SystemSlugs.BEZERRO_FEMEA],
                'target': categories[AnimalCategory.SystemSlugs.NOVILHA_2A],
                'quantity': quantity_females,
            })

        # 4. EXECUTAR TODAS AS MUDANÇAS DENTRO DA MESMA TRANSAÇÃO
        results = []

        for op in operations:
            source_cat = op['source']
            target_cat = op['target']
            qty = op['quantity']

            saida_metadata = {
                **base_metadata,
                'tipo_transferencia': 'desmame',
                'categoria_origem': source_cat.name,
                'categoria_destino': target_cat.name,
                'categoria_destino_id': str(target_cat.id),
            }

            entrada_metadata = {
                **base_metadata,
                'tipo_transferencia': 'desmame',
                'categoria_origem': source_cat.name,
                'categoria_origem_id': str(source_cat.id),
                'categoria_destino': target_cat.name,
            }

            # SAÍDA: remover da categoria origem
            movimento_saida = MovementService.execute_saida(
                farm_id=farm_id,
                animal_category_id=str(source_cat.id),
                operation_type=OperationType.DESMAME_OUT,
                quantity=qty,
                user=user,
                timestamp=operation_timestamp,
                metadata=saida_metadata,
                ip_address=ip_address,
            )

            # ENTRADA: adicionar na categoria destino
            movimento_entrada = MovementService.execute_entrada(
                farm_id=farm_id,
                animal_category_id=str(target_cat.id),
                operation_type=OperationType.DESMAME_IN,
                quantity=qty,
                user=user,
                timestamp=operation_timestamp,
                metadata=entrada_metadata,
                ip_address=ip_address,
            )

            results.append((movimento_saida, movimento_entrada))

        return results

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def get_transfer_summary(
        movimento_saida: AnimalMovement,
        movimento_entrada: AnimalMovement
    ) -> Dict[str, Any]:
        """Retorna um resumo legível da transferência."""
        op_type = movimento_saida.operation_type

        if op_type == OperationType.MANEJO_OUT.value:
            return {
                'tipo': 'Manejo',
                'origem': movimento_saida.farm_stock_balance.farm.name,
                'destino': movimento_entrada.farm_stock_balance.farm.name,
                'categoria': movimento_saida.farm_stock_balance.animal_category.name,
                'quantidade': movimento_saida.quantity,
                'data': movimento_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
                'usuario': movimento_saida.created_by.username,
            }
        elif op_type == OperationType.DESMAME_OUT.value:
            return {
                'tipo': 'Desmame',
                'fazenda': movimento_saida.farm_stock_balance.farm.name,
                'categoria_origem': movimento_saida.farm_stock_balance.animal_category.name,
                'categoria_destino': movimento_entrada.farm_stock_balance.animal_category.name,
                'quantidade': movimento_saida.quantity,
                'data': movimento_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
                'usuario': movimento_saida.created_by.username,
            }
        else:
            return {
                'tipo': 'Mudança de Categoria',
                'fazenda': movimento_saida.farm_stock_balance.farm.name,
                'categoria_origem': movimento_saida.farm_stock_balance.animal_category.name,
                'categoria_destino': movimento_entrada.farm_stock_balance.animal_category.name,
                'quantidade': movimento_saida.quantity,
                'data': movimento_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
                'usuario': movimento_saida.created_by.username,
            }

    @staticmethod
    def get_desmame_summary(
        results: List[Tuple[AnimalMovement, AnimalMovement]]
    ) -> Dict[str, Any]:
        """
        Retorna resumo completo de uma operação de desmame.

        Args:
            results: Lista retornada por execute_desmame()

        Returns:
            dict com detalhes da operação completa
        """
        if not results:
            return {'tipo': 'Desmame', 'operacoes': []}

        first_saida = results[0][0]

        summary = {
            'tipo': 'Desmame',
            'fazenda': first_saida.farm_stock_balance.farm.name,
            'data': first_saida.timestamp.strftime('%d/%m/%Y %H:%M'),
            'usuario': first_saida.created_by.username,
            'total_animais': sum(r[0].quantity for r in results),
            'operacoes': [],
        }

        for saida, entrada in results:
            summary['operacoes'].append({
                'categoria_origem': saida.farm_stock_balance.animal_category.name,
                'categoria_destino': entrada.farm_stock_balance.animal_category.name,
                'quantidade': saida.quantity,
            })

        return summary
"""
test_stock_integrity.py — Invariante crítica: saldo NUNCA pode ser negativo.

Testa todos os caminhos que poderiam violar essa regra:
  - Saída maior que o saldo disponível
  - Saída exata com saldo zero
  - Quantidade inválida (zero, negativa)
  - Operação de saída em saldo inexistente
  - Consistência do snapshot com o ledger após falha
"""
import pytest
from django.core.exceptions import ValidationError

from inventory.services import MovementService
from inventory.domain.value_objects import OperationType
from inventory.domain.exceptions import (
    InsufficientStockError,
    InvalidQuantityError,
    StockBalanceNotFoundError,
)
from inventory.models import FarmStockBalance


@pytest.mark.django_db
class TestSaldoNuncaNegativo:
    """A invariante mais crítica do sistema."""

    def test_saida_maior_que_saldo_lanca_excecao(
        self, stock_balance_with_animals, farm, category, db_user
    ):
        """Saldo = 20. Tenta sair 21. Deve lançar InsufficientStockError."""
        with pytest.raises(InsufficientStockError) as exc_info:
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=21,
                user=db_user,
            )
        assert exc_info.value.requested == 21
        assert exc_info.value.available == 20

    def test_saida_maior_nao_altera_saldo(
        self, stock_balance_with_animals, farm, category, db_user
    ):
        """Após falha, o saldo deve permanecer intacto."""
        saldo_antes = stock_balance_with_animals.current_quantity

        with pytest.raises(InsufficientStockError):
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=999,
                user=db_user,
            )

        stock_balance_with_animals.refresh_from_db()
        assert stock_balance_with_animals.current_quantity == saldo_antes

    def test_saida_maior_nao_cria_movimento_no_ledger(
        self, stock_balance_with_animals, farm, category, db_user
    ):
        """Nenhum registro deve ser criado no ledger após falha."""
        from inventory.models import AnimalMovement
        total_antes = AnimalMovement.objects.count()

        with pytest.raises(InsufficientStockError):
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=999,
                user=db_user,
            )

        assert AnimalMovement.objects.count() == total_antes

    def test_saida_de_saldo_zero_lanca_excecao(
        self, stock_balance, farm, category, db_user
    ):
        """Saldo = 0. Qualquer saída deve falhar."""
        assert stock_balance.current_quantity == 0

        with pytest.raises(InsufficientStockError):
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=1,
                user=db_user,
            )

    def test_quantidade_zero_lanca_excecao_entrada(
        self, stock_balance, farm, category, db_user
    ):
        with pytest.raises((InvalidQuantityError, Exception)):
            MovementService.execute_entrada(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.NASCIMENTO,
                quantity=0,
                user=db_user,
            )

    def test_quantidade_zero_lanca_excecao_saida(
        self, stock_balance_with_animals, farm, category, db_user
    ):
        with pytest.raises((InvalidQuantityError, Exception)):
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=0,
                user=db_user,
            )

    def test_quantidade_negativa_lanca_excecao(
        self, stock_balance, farm, category, db_user
    ):
        with pytest.raises((InvalidQuantityError, Exception)):
            MovementService.execute_entrada(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.NASCIMENTO,
                quantity=-5,
                user=db_user,
            )

    def test_constraint_banco_impede_saldo_negativo(self, stock_balance):
        """
        Última linha de defesa: a constraint CHECK do banco.
        Mesmo forçando via ORM, o banco deve rejeitar.
        """
        from django.db import IntegrityError

        with pytest.raises((IntegrityError, ValidationError)):
            # Força direto no ORM, bypassando o service
            stock_balance.current_quantity = -1
            stock_balance.save()

    def test_mensagem_erro_contem_informacoes_uteis(
        self, stock_balance_with_animals, farm, category, db_user
    ):
        """A mensagem de erro deve identificar fazenda e categoria."""
        with pytest.raises(InsufficientStockError) as exc_info:
            MovementService.execute_saida(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.ABATE,
                quantity=100,
                user=db_user,
            )
        error = exc_info.value
        assert farm.name in error.message
        assert category.name in error.message


@pytest.mark.django_db
class TestSaldoNaoEncontrado:

    def test_saldo_inexistente_lanca_excecao(self, farm, db_user):
        """Tenta operar em fazenda sem categoria cadastrada."""
        import uuid
        with pytest.raises((StockBalanceNotFoundError, Exception)):
            MovementService.execute_entrada(
                farm_id=str(farm.id),
                animal_category_id=str(uuid.uuid4()),  # UUID inexistente
                operation_type=OperationType.NASCIMENTO,
                quantity=5,
                user=db_user,
            )
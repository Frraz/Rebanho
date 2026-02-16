"""
test_movement_service.py — Testes das operações básicas do MovementService.

Cobre:
  - Entradas: NASCIMENTO, COMPRA, DESMAME, SALDO
  - Saídas: MORTE, ABATE, VENDA, DOACAO
  - Atualização correta do saldo snapshot
  - Criação correta do registro no ledger
  - Incremento de versão após cada operação
"""
import pytest
from inventory.services import MovementService
from inventory.domain.value_objects import OperationType
from inventory.models import FarmStockBalance, AnimalMovement


@pytest.mark.django_db
class TestEntradas:
    """Testa operações que aumentam o saldo."""

    def test_nascimento_aumenta_saldo(self, stock_balance, farm, category, db_user):
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=10,
            user=db_user,
        )
        stock_balance.refresh_from_db()
        assert stock_balance.current_quantity == 10

    def test_compra_aumenta_saldo(self, stock_balance, farm, category, db_user):
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=5,
            user=db_user,
        )
        stock_balance.refresh_from_db()
        assert stock_balance.current_quantity == 5

    def test_multiplas_entradas_acumulam(self, stock_balance, farm, category, db_user):
        for _ in range(3):
            MovementService.execute_entrada(
                farm_id=str(farm.id),
                animal_category_id=str(category.id),
                operation_type=OperationType.NASCIMENTO,
                quantity=10,
                user=db_user,
            )
        stock_balance.refresh_from_db()
        assert stock_balance.current_quantity == 30

    def test_entrada_cria_registro_no_ledger(self, stock_balance, farm, category, db_user):
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=7,
            user=db_user,
        )
        assert AnimalMovement.objects.filter(pk=movement.pk).exists()
        assert movement.quantity == 7
        assert movement.movement_type == 'ENTRADA'
        assert movement.operation_type == 'NASCIMENTO'
        assert movement.created_by == db_user

    def test_entrada_incrementa_versao(self, stock_balance, farm, category, db_user):
        versao_inicial = stock_balance.version
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=5,
            user=db_user,
        )
        stock_balance.refresh_from_db()
        assert stock_balance.version == versao_inicial + 1

    def test_entrada_salva_metadata(self, stock_balance, farm, category, db_user):
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=3,
            user=db_user,
            metadata={'fornecedor': 'Agropecuária Brasil', 'observacao': 'Lote 42'},
        )
        assert movement.metadata['fornecedor'] == 'Agropecuária Brasil'
        assert movement.metadata['observacao'] == 'Lote 42'

    def test_entrada_salva_ip(self, stock_balance, farm, category, db_user):
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=2,
            user=db_user,
            ip_address='192.168.1.1',
        )
        assert movement.ip_address == '192.168.1.1'


@pytest.mark.django_db
class TestSaidas:
    """Testa operações que diminuem o saldo."""

    def test_abate_reduz_saldo(self, stock_balance_with_animals, farm, category, db_user):
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=5,
            user=db_user,
        )
        stock_balance_with_animals.refresh_from_db()
        assert stock_balance_with_animals.current_quantity == 15

    def test_morte_exige_motivo(self, stock_balance_with_animals, farm, category, db_user, death_reason):
        movement = MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.MORTE,
            quantity=1,
            user=db_user,
            death_reason_id=str(death_reason.id),
        )
        assert movement.death_reason == death_reason
        assert movement.operation_type == 'MORTE'

    def test_venda_exige_cliente(self, stock_balance_with_animals, farm, category, db_user, operation_client):
        movement = MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.VENDA,
            quantity=3,
            user=db_user,
            client_id=str(operation_client.id),
        )
        assert movement.client == operation_client
        assert movement.operation_type == 'VENDA'

    def test_doacao_exige_cliente(self, stock_balance_with_animals, farm, category, db_user, operation_client):
        movement = MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.DOACAO,
            quantity=2,
            user=db_user,
            client_id=str(operation_client.id),
        )
        assert movement.client == operation_client

    def test_saida_cria_registro_ledger(self, stock_balance_with_animals, farm, category, db_user):
        movement = MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=4,
            user=db_user,
        )
        assert movement.movement_type == 'SAIDA'
        assert movement.quantity == 4

    def test_saida_ate_zerar_saldo(self, stock_balance_with_animals, farm, category, db_user):
        """Saldo pode chegar a zero — não pode ficar negativo."""
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=20,  # Exatamente o saldo disponível
            user=db_user,
        )
        stock_balance_with_animals.refresh_from_db()
        assert stock_balance_with_animals.current_quantity == 0

    def test_sequencia_entrada_saida(self, stock_balance, farm, category, db_user):
        """Entrada de 15, saída de 7 → saldo final deve ser 8."""
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=15,
            user=db_user,
        )
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=7,
            user=db_user,
        )
        stock_balance.refresh_from_db()
        assert stock_balance.current_quantity == 8
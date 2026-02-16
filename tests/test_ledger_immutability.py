"""
test_ledger_immutability.py — Ledger é APPEND-ONLY.

Verifica que AnimalMovement não pode ser alterado ou deletado após criação.
Esta é uma proteção fundamental de integridade do sistema.

Testa:
  - Tentativa de update em movimento existente → ValidationError
  - Tentativa de delete em movimento existente → ValidationError
  - Criação de novo movimento sempre funciona (append)
  - Ledger pode ser recalculado a qualquer momento
"""
import pytest
from django.core.exceptions import ValidationError

from inventory.services import MovementService
from inventory.domain.value_objects import OperationType
from inventory.models import AnimalMovement


@pytest.mark.django_db
class TestLedgerImutavel:

    def test_movimento_nao_pode_ser_alterado(
        self, stock_balance, farm, category, db_user
    ):
        """Tentar salvar um movimento existente deve lançar ValidationError."""
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=10,
            user=db_user,
        )

        # Tenta modificar o registro existente
        movement.quantity = 999
        with pytest.raises(ValidationError) as exc_info:
            movement.save()

        assert 'imutáv' in exc_info.value.message.lower() or \
               'imutav' in exc_info.value.message.lower() or \
               'ledger' in exc_info.value.message.lower()

    def test_movimento_nao_pode_ser_deletado(
        self, stock_balance, farm, category, db_user
    ):
        """Tentar deletar um movimento deve lançar ValidationError."""
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=5,
            user=db_user,
        )

        with pytest.raises(ValidationError) as exc_info:
            movement.delete()

        # Movimento ainda existe no banco
        assert AnimalMovement.objects.filter(pk=movement.pk).exists()

    def test_quantidade_no_banco_nao_muda_apos_tentativa_de_edicao(
        self, stock_balance, farm, category, db_user
    ):
        """Quantidade original deve ser preservada após tentativa de alteração."""
        movement = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=10,
            user=db_user,
        )

        try:
            movement.quantity = 999
            movement.save()
        except ValidationError:
            pass

        movement.refresh_from_db()
        assert movement.quantity == 10  # Permanece 10

    def test_novo_movimento_sempre_pode_ser_criado(
        self, stock_balance, farm, category, db_user
    ):
        """Append é sempre permitido — apenas updates e deletes são bloqueados."""
        m1 = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=5,
            user=db_user,
        )
        m2 = MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=3,
            user=db_user,
        )
        assert m1.pk != m2.pk
        assert AnimalMovement.objects.count() >= 2

    def test_ledger_pode_ser_recalculado_a_partir_do_historico(
        self, stock_balance, farm, category, db_user
    ):
        """
        O saldo atual deve ser igual à soma das entradas menos as saídas
        calculada a partir do ledger (sem usar o snapshot).
        """
        from django.db.models import Sum, Q

        # Cria histórico: +10, +5, −3 → esperado = 12
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.NASCIMENTO,
            quantity=10, user=db_user,
        )
        MovementService.execute_entrada(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.COMPRA,
            quantity=5, user=db_user,
        )
        MovementService.execute_saida(
            farm_id=str(farm.id),
            animal_category_id=str(category.id),
            operation_type=OperationType.ABATE,
            quantity=3, user=db_user,
        )

        # Calcula saldo direto do ledger (sem snapshot)
        entradas = AnimalMovement.objects.filter(
            farm_stock_balance=stock_balance,
            movement_type='ENTRADA'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saidas = AnimalMovement.objects.filter(
            farm_stock_balance=stock_balance,
            movement_type='SAIDA'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saldo_calculado = entradas - saidas

        # Compara com o snapshot
        stock_balance.refresh_from_db()
        assert saldo_calculado == stock_balance.current_quantity == 12
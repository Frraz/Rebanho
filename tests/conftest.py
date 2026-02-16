"""
conftest.py — Fixtures compartilhadas para toda a suíte de testes.

ATENÇÃO: A fixture do pytest-django se chama `client` (django.test.Client).
Para evitar conflito, a fixture do modelo Client (cliente de operações)
se chama `operation_client`.
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# USUÁRIO
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_user(db):
    """Usuário ativo padrão para testes."""
    return User.objects.create_user(
        username='testuser',
        password='testpass123',
        is_active=True,
    )


@pytest.fixture
def staff_user(db):
    """Usuário staff para testes de aprovação e auditoria."""
    return User.objects.create_user(
        username='staffuser',
        password='testpass123',
        is_active=True,
        is_staff=True,
        email='staff@test.com',
    )


# ──────────────────────────────────────────────────────────────────
# FAZENDA
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def farm(db):
    """Fazenda ativa para testes."""
    from farms.models import Farm
    return Farm.objects.create(name='Fazenda Teste', is_active=True)


@pytest.fixture
def farm_b(db):
    """Segunda fazenda para testes de manejo entre fazendas."""
    from farms.models import Farm
    return Farm.objects.create(name='Fazenda Destino', is_active=True)


# ──────────────────────────────────────────────────────────────────
# CATEGORIA
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def category(db):
    """Categoria de animal padrão."""
    from inventory.models import AnimalCategory
    return AnimalCategory.objects.create(name='Bezerro', is_active=True)


@pytest.fixture
def category_b(db):
    """Segunda categoria para testes de mudança de categoria."""
    from inventory.models import AnimalCategory
    return AnimalCategory.objects.create(name='Novilho', is_active=True)


# ──────────────────────────────────────────────────────────────────
# SALDO (stock_balance)
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def stock_balance(db, farm, category):
    """Saldo zerado para fazenda + categoria padrão."""
    from inventory.models import FarmStockBalance
    balance, _ = FarmStockBalance.objects.get_or_create(
        farm=farm,
        animal_category=category,
        defaults={'current_quantity': 0},
    )
    return balance


@pytest.fixture
def stock_balance_with_animals(db, farm, category):
    """Saldo com 20 animais — pronto para testes de saída."""
    from inventory.models import FarmStockBalance
    balance, _ = FarmStockBalance.objects.get_or_create(
        farm=farm,
        animal_category=category,
        defaults={'current_quantity': 0},
    )
    FarmStockBalance.objects.filter(pk=balance.pk).update(current_quantity=20)
    balance.refresh_from_db()
    return balance


@pytest.fixture
def stock_balance_b(db, farm_b, category):
    """Saldo zerado na fazenda destino."""
    from inventory.models import FarmStockBalance
    balance, _ = FarmStockBalance.objects.get_or_create(
        farm=farm_b,
        animal_category=category,
        defaults={'current_quantity': 0},
    )
    return balance


@pytest.fixture
def stock_balance_cat_b(db, farm, category_b):
    """Saldo zerado para segunda categoria na mesma fazenda."""
    from inventory.models import FarmStockBalance
    balance, _ = FarmStockBalance.objects.get_or_create(
        farm=farm,
        animal_category=category_b,
        defaults={'current_quantity': 0},
    )
    return balance


# ──────────────────────────────────────────────────────────────────
# OPERAÇÕES
# IMPORTANTE: nomeada `operation_client` para não conflitar com
# o `client` nativo do pytest-django (django.test.Client HTTP)
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def operation_client(db):
    """Cliente de operações (venda/doação). NÃO confundir com django.test.Client."""
    from operations.models import Client
    return Client.objects.create(name='João da Silva')


@pytest.fixture
def death_reason(db):
    """Motivo de morte para testes de ocorrência de morte."""
    from operations.models import DeathReason
    return DeathReason.objects.create(name='Doença')
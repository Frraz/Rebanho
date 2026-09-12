"""
Testes do SaleService — venda multi-lote, estoque e extrato do cliente.

É aqui que dinheiro e estoque se encontram, então é aqui que os testes
importam mais. Os casos cobrem justamente o que o desenho tem de delicado:
a mesma categoria repetida em duas linhas, a atomicidade quando uma linha
falha, e o que acontece com o saldo do cliente ao editar ou apagar a venda.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from finance.models import EntrySource, EntryType, FinancialEntry, Sale, SaleStatus
from finance.services import BalanceService, SaleService
from inventory.models import AnimalMovement, FarmStockBalance


def _item(category, quantity, peso=None, preco_kg=None, total=None):
    return {
        'animal_category': category,
        'quantity': quantity,
        'total_weight': Decimal(peso) if peso is not None else None,
        'price_per_kg': Decimal(preco_kg) if preco_kg is not None else None,
        'total_amount': Decimal(total) if total is not None else None,
    }


def _saldo_estoque(farm, category):
    return FarmStockBalance.objects.get(
        farm=farm, animal_category=category
    ).current_quantity


# ══════════════════════════════════════════════════════════════════════════
# CRIAÇÃO
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_venda_simples_baixa_estoque_e_gera_debito(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    venda = SaleService.create(
        client=operation_client,
        farm=farm,
        date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )

    assert venda.total_quantity == 5
    assert venda.total_amount == Decimal('10000.00')
    assert _saldo_estoque(farm, category) == 15

    # O cliente passa a dever: saldo negativo.
    assert BalanceService.get_balance(operation_client.id) == Decimal('-10000.00')

    entry = FinancialEntry.objects.get(sale=venda)
    assert entry.entry_type == EntryType.DEBITO
    assert entry.source_type == EntrySource.VENDA
    assert entry.amount == Decimal('10000.00')


@pytest.mark.django_db
def test_venda_com_varios_tipos_de_animal(
    farm, category, category_b, operation_client, db_user,
    stock_balance_with_animals, stock_balance_cat_b
):
    FarmStockBalance.objects.filter(
        farm=farm, animal_category=category_b
    ).update(current_quantity=10)

    venda = SaleService.create(
        client=operation_client,
        farm=farm,
        date='2026-09-10',
        items=[
            _item(category, 5, '1000.00', '10.00', '10000.00'),
            _item(category_b, 3, '900.00', '12.00', '10800.00'),
        ],
        user=db_user,
    )

    assert venda.items.count() == 2
    assert venda.total_quantity == 8
    assert venda.total_amount == Decimal('20800.00')
    assert _saldo_estoque(farm, category) == 15
    assert _saldo_estoque(farm, category_b) == 7

    # Uma venda gera UM débito, com a soma dos lotes.
    assert FinancialEntry.objects.filter(sale=venda).count() == 1


@pytest.mark.django_db
def test_mesma_categoria_em_duas_linhas_soma_as_quantidades(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """Dois lotes do mesmo tipo, com preços por quilo diferentes."""
    venda = SaleService.create(
        client=operation_client,
        farm=farm,
        date='2026-09-10',
        items=[
            _item(category, 5, '1000.00', '10.00', '10000.00'),
            _item(category, 3, '600.00', '12.00', '7200.00'),
        ],
        user=db_user,
    )

    assert venda.items.count() == 2
    assert venda.total_quantity == 8
    # 20 − 5 − 3: a segunda linha enxerga o saldo já descontado pela primeira.
    assert _saldo_estoque(farm, category) == 12
    assert venda.total_amount == Decimal('17200.00')


@pytest.mark.django_db
def test_recusa_venda_quando_a_soma_das_linhas_estoura_o_estoque(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """
    Cada linha isolada cabe nos 20 animais; a soma (15 + 10) não cabe.

    É exatamente o caso que uma validação linha a linha deixaria passar.
    """
    with pytest.raises(ValidationError):
        SaleService.create(
            client=operation_client,
            farm=farm,
            date='2026-09-10',
            items=[
                _item(category, 15, '3000.00', '10.00', '30000.00'),
                _item(category, 10, '2000.00', '10.00', '20000.00'),
            ],
            user=db_user,
        )

    # Nada pode ter sido gravado.
    assert _saldo_estoque(farm, category) == 20
    assert Sale.objects.count() == 0
    assert AnimalMovement.objects.filter(operation_type='VENDA').count() == 0
    assert FinancialEntry.objects.count() == 0


@pytest.mark.django_db
def test_venda_sem_preco_nao_gera_lancamento(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """O caso das vendas antigas importadas: baixa estoque, mas não vira dívida."""
    venda = SaleService.create(
        client=operation_client,
        farm=farm,
        date='2026-09-10',
        items=[_item(category, 5, '1000.00')],
        user=db_user,
    )

    assert venda.total_amount is None
    assert venda.has_price is False
    assert _saldo_estoque(farm, category) == 15
    assert FinancialEntry.objects.count() == 0
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')


@pytest.mark.django_db
def test_metadata_do_movimento_mantem_compatibilidade(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """
    Os relatórios antigos leem `peso` e `preco_total` do metadata.
    Se estas chaves sumirem, o Relatório por Fazenda quebra silenciosamente.
    """
    venda = SaleService.create(
        client=operation_client,
        farm=farm,
        date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
        notes='Lote da seca',
    )

    movimento = venda.items.first().movement
    assert movimento.metadata['peso'] == '1000.00'
    assert movimento.metadata['preco_total'] == '10000.00'
    assert movimento.metadata['observacao'] == 'Lote da seca'
    assert movimento.metadata['_sale_id'] == str(venda.id)
    # Nunca float: o JSON tem que guardar texto de Decimal.
    assert isinstance(movimento.metadata['preco_total'], str)


@pytest.mark.django_db
def test_venda_sem_linhas_e_recusada(farm, operation_client, db_user):
    with pytest.raises(ValidationError):
        SaleService.create(
            client=operation_client, farm=farm, date='2026-09-10',
            items=[], user=db_user,
        )


# ══════════════════════════════════════════════════════════════════════════
# EDIÇÃO
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_editar_venda_ajusta_estoque_e_saldo(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    assert _saldo_estoque(farm, category) == 15

    SaleService.update(
        sale=venda, client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 8, '1600.00', '10.00', '16000.00')],
        user=db_user,
    )

    venda.refresh_from_db()
    assert venda.total_quantity == 8
    assert venda.total_amount == Decimal('16000.00')
    assert _saldo_estoque(farm, category) == 12
    assert BalanceService.get_balance(operation_client.id) == Decimal('-16000.00')
    # Continua havendo exatamente um débito — não dois.
    assert FinancialEntry.objects.filter(sale=venda).count() == 1


@pytest.mark.django_db
def test_editar_apenas_o_preco_nao_e_barrado_por_estoque(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """
    Regressão: a edição devolve o estoque antes de validar a nova composição.
    Sem isso, trocar só o preço de uma venda que consome todo o estoque seria
    recusada por "estoque insuficiente" contra o saldo que ela mesma ocupa.
    """
    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 20, '4000.00', '10.00', '40000.00')],
        user=db_user,
    )
    assert _saldo_estoque(farm, category) == 0

    SaleService.update(
        sale=venda, client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 20, '4000.00', '11.00', '44000.00')],
        user=db_user,
    )

    venda.refresh_from_db()
    assert venda.total_amount == Decimal('44000.00')
    assert _saldo_estoque(farm, category) == 0


@pytest.mark.django_db
def test_editar_removendo_o_preco_apaga_o_debito(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    SaleService.update(
        sale=venda, client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00')],
        user=db_user,
    )

    assert FinancialEntry.objects.filter(sale=venda).count() == 0
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')


# ══════════════════════════════════════════════════════════════════════════
# EXCLUSÃO
# ══════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
def test_apagar_venda_devolve_estoque_e_limpa_o_saldo(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    movimento_id = venda.items.first().movement_id

    SaleService.delete(sale=venda, user=db_user, reason='Registro duplicado')

    assert _saldo_estoque(farm, category) == 20
    assert Sale.objects.count() == 0
    assert FinancialEntry.objects.count() == 0
    assert not AnimalMovement.objects.filter(id=movimento_id).exists()
    assert BalanceService.get_balance(operation_client.id) == Decimal('0.00')


@pytest.mark.django_db
def test_apagar_venda_registra_o_log_de_exclusao(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """
    A venda some da tela de auditoria quando é apagada — o log é a única
    trilha que resta, então ele precisa guardar o retrato completo.
    """
    from finance.models import FinanceDeletionLog

    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    SaleService.delete(sale=venda, user=db_user, reason='Erro de digitação')

    log = FinanceDeletionLog.objects.get()
    assert log.object_type == 'VENDA'
    assert log.amount == Decimal('10000.00')
    assert log.reason == 'Erro de digitação'
    assert log.deleted_by == db_user
    assert log.snapshot['venda']['cliente'] == operation_client.name
    assert len(log.snapshot['lotes']) == 1
    assert log.snapshot['lotes'][0]['quantidade'] == 5


@pytest.mark.django_db
def test_nao_apaga_venda_com_lote_ja_estornado(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    """
    O registro de estorno é imutável por contrato e protege a movimentação.
    Recusamos com mensagem clara em vez de deixar estourar um erro de banco.
    """
    from inventory.models import AnimalMovementCancellation

    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    AnimalMovementCancellation.objects.create(
        movement=venda.items.first().movement,
        cancelled_by=db_user,
        quantity_restored=5,
        balance_before=15,
        balance_after=20,
    )

    with pytest.raises(ValidationError):
        SaleService.delete(sale=venda, user=db_user)

    with pytest.raises(ValidationError):
        SaleService.update(
            sale=venda, client=operation_client, farm=farm, date='2026-09-10',
            items=[_item(category, 2, '400.00', '10.00', '4000.00')],
            user=db_user,
        )

    assert Sale.objects.filter(pk=venda.pk).exists()


@pytest.mark.django_db
def test_venda_cancelada_nao_pode_ser_editada(
    farm, category, operation_client, db_user, stock_balance_with_animals
):
    venda = SaleService.create(
        client=operation_client, farm=farm, date='2026-09-10',
        items=[_item(category, 5, '1000.00', '10.00', '10000.00')],
        user=db_user,
    )
    Sale.objects.filter(pk=venda.pk).update(status=SaleStatus.CANCELADA)
    venda.refresh_from_db()

    with pytest.raises(ValidationError):
        SaleService.update(
            sale=venda, client=operation_client, farm=farm, date='2026-09-10',
            items=[_item(category, 2, '400.00', '10.00', '4000.00')],
            user=db_user,
        )

"""
Importa para o módulo financeiro todas as vendas já cadastradas no sistema.

O QUE FAZ
    Cada `AnimalMovement` com `operation_type='VENDA'` vira um par
    `Sale` + `SaleItem` (um para um). Quando o movimento tem preço, nasce
    também o `FinancialEntry` de débito — é isso que faz o saldo de cada
    cliente já começar refletindo tudo o que ele comprou.

O QUE NÃO FAZ
    • Não agrupa vendas antigas em vendas multi-lote. Juntar movimentos do
      mesmo cliente/data/fazenda seria adivinhação: não há como saber se foram
      uma venda só ou várias. Um para um é o único mapeamento reversível.
    • Não toca em estoque. Os saldos já refletem esses movimentos; recalcular
      qualquer coisa aqui seria duplicar a baixa.
    • Não inventa valor. Venda sem preço continua sem preço — fica visível na
      lista, marcada como "sem valor", e o usuário completa quando quiser.

SEGURANÇA
    • Idempotente: pula movimentos que já tenham um lote vinculado, então pode
      rodar de novo sem duplicar nada.
    • Reversível: as vendas criadas aqui ficam marcadas com `origin='BACKFILL'`
      e o `reverse` apaga exatamente essas — nunca as cadastradas pelo usuário,
      e nunca um `AnimalMovement`.
    • Usa `apps.get_model()`, não os modelos reais: evita disparar `full_clean`,
      signals e histórico durante a migração.
"""
import logging
from decimal import Decimal

from django.db import migrations

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
QUATRO_CASAS = Decimal('0.0001')


def _parse(value):
    """
    Lê um valor monetário/peso do `metadata`.

    Delega para `finance.utils.money`, que é código puro (sem ORM) e trata a
    diferença crítica entre o que o usuário digitou e o que foi gravado:
    numa string sem vírgula, o ponto é separador DECIMAL — reinterpretá-lo
    como milhar inflaria o valor em 1000×.
    """
    from finance.utils.money import parse_stored_amount

    return parse_stored_amount(value)


def _parse_money(value):
    from finance.utils.money import parse_stored_money

    return parse_stored_money(value)


def _parse_weight(value):
    from finance.utils.money import parse_stored_weight

    return parse_stored_weight(value)


def importar_vendas(apps, schema_editor):
    AnimalMovement = apps.get_model('inventory', 'AnimalMovement')
    AnimalMovementCancellation = apps.get_model('inventory', 'AnimalMovementCancellation')
    Sale = apps.get_model('finance', 'Sale')
    SaleItem = apps.get_model('finance', 'SaleItem')
    FinancialEntry = apps.get_model('finance', 'FinancialEntry')

    # Idempotência: o que já foi importado antes não entra de novo.
    ja_importados = set(
        SaleItem.objects.filter(movement__isnull=False).values_list('movement_id', flat=True)
    )
    cancelados = set(
        AnimalMovementCancellation.objects.values_list('movement_id', flat=True)
    )

    contagem = {
        'importadas': 0,
        'com_valor': 0,
        'sem_valor': 0,
        'canceladas': 0,
        'valor_ilegivel': 0,
        'sem_cliente': 0,
        'ja_importadas': 0,
    }
    sem_cliente_ids = []

    movimentos = (
        AnimalMovement.objects
        .filter(operation_type='VENDA')
        .select_related('farm_stock_balance')
        .order_by('timestamp', 'created_at')
        .iterator(chunk_size=2000)
    )

    vendas_lote, itens_lote, lancamentos_lote = [], [], []

    def descarregar():
        """Grava o lote acumulado e limpa os buffers."""
        if vendas_lote:
            Sale.objects.bulk_create(vendas_lote, batch_size=BATCH_SIZE)
        if itens_lote:
            SaleItem.objects.bulk_create(itens_lote, batch_size=BATCH_SIZE)
        if lancamentos_lote:
            FinancialEntry.objects.bulk_create(lancamentos_lote, batch_size=BATCH_SIZE)
        vendas_lote.clear()
        itens_lote.clear()
        lancamentos_lote.clear()

    for mov in movimentos:
        if mov.id in ja_importados:
            contagem['ja_importadas'] += 1
            continue

        # VENDA exige cliente por regra de modelo, mas dados antigos podem ter
        # escapado. Registramos e seguimos em vez de abortar a migração inteira.
        if mov.client_id is None:
            contagem['sem_cliente'] += 1
            sem_cliente_ids.append(str(mov.id))
            continue

        metadata = mov.metadata or {}
        bruto_preco = metadata.get('preco_total')
        peso = _parse_weight(metadata.get('peso'))
        valor = _parse_money(bruto_preco)

        # Havia algo escrito no campo de preço, mas não deu para interpretar.
        # Contamos separadamente de "sem valor" para o resumo final distinguir
        # a venda que nunca teve preço da que teve um preço corrompido.
        if valor is None and bruto_preco is not None and _parse(bruto_preco) is None:
            contagem['valor_ilegivel'] += 1

        foi_cancelada = mov.id in cancelados
        status = 'CANCELADA' if foi_cancelada else 'ATIVA'

        preco_kg = None
        if valor is not None and peso is not None and peso > 0:
            # Reconstrói o preço por quilo a partir do que existe, para a venda
            # importada abrir no formulário novo já preenchida.
            preco_kg = (valor / peso).quantize(QUATRO_CASAS)

        venda = Sale(
            client_id=mov.client_id,
            farm_id=mov.farm_stock_balance.farm_id,
            date=mov.timestamp,
            notes=str(metadata.get('observacao') or ''),
            status=status,
            origin='BACKFILL',
            total_quantity=mov.quantity,
            total_weight=peso,
            total_amount=valor,
            created_by_id=mov.created_by_id,
        )
        vendas_lote.append(venda)

        itens_lote.append(SaleItem(
            sale_id=venda.id,
            animal_category_id=mov.farm_stock_balance.animal_category_id,
            movement_id=mov.id,
            quantity=mov.quantity,
            total_weight=peso,
            price_per_kg=preco_kg,
            total_amount=valor,
            line_order=0,
        ))

        contagem['importadas'] += 1

        if foi_cancelada:
            contagem['canceladas'] += 1
        elif valor is not None:
            lancamentos_lote.append(FinancialEntry(
                client_id=mov.client_id,
                date=mov.timestamp,
                entry_type='DEBITO',
                amount=valor,
                source_type='VENDA',
                sale_id=venda.id,
                description=f"Venda de {mov.quantity} animal(is)",
                created_by_id=mov.created_by_id,
            ))
            contagem['com_valor'] += 1
        else:
            contagem['sem_valor'] += 1

        if len(vendas_lote) >= BATCH_SIZE:
            descarregar()

    descarregar()

    resumo = (
        "[BACKFILL FINANCEIRO] "
        f"Vendas importadas: {contagem['importadas']} | "
        f"com valor (viraram dívida): {contagem['com_valor']} | "
        f"sem valor (a completar): {contagem['sem_valor']} | "
        f"canceladas (sem efeito no saldo): {contagem['canceladas']} | "
        f"preço ilegível: {contagem['valor_ilegivel']} | "
        f"sem cliente (ignoradas): {contagem['sem_cliente']} | "
        f"já importadas antes: {contagem['ja_importadas']}"
    )
    logger.warning(resumo)
    print(f"\n{resumo}")

    if sem_cliente_ids:
        aviso = (
            "[BACKFILL FINANCEIRO] ATENÇÃO — movimentos de VENDA sem cliente "
            f"foram ignorados e precisam de correção manual: "
            f"{', '.join(sem_cliente_ids[:20])}"
            f"{' ...' if len(sem_cliente_ids) > 20 else ''}"
        )
        logger.error(aviso)
        print(aviso)


def desfazer_importacao(apps, schema_editor):
    """
    Desfaz o backfill apagando SOMENTE o que ele criou.

    As vendas cadastradas pelo usuário (`origin='APP'`) ficam intactas, e
    nenhum `AnimalMovement` é tocado — o ledger de estoque permanece exatamente
    como estava.
    """
    Sale = apps.get_model('finance', 'Sale')

    importadas = Sale.objects.filter(origin='BACKFILL')
    total = importadas.count()
    # SaleItem e FinancialEntry são CASCADE a partir de Sale.
    importadas.delete()

    msg = f"[BACKFILL FINANCEIRO] Revertido: {total} venda(s) importada(s) removida(s)."
    logger.warning(msg)
    print(f"\n{msg}")


class Migration(migrations.Migration):

    atomic = True

    dependencies = [
        ("finance", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(importar_vendas, desfazer_importacao),
    ]

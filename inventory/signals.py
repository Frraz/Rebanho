"""
Inventory Signals - Automações ao criar/modificar categorias.

REGRA DE NEGÓCIO CRÍTICA:
Quando uma nova categoria de animal é criada, automaticamente devem ser
criados registros de saldo (FarmStockBalance) para TODAS as fazendas
ativas, inicializados com quantidade = 0.

Isso garante que ao visualizar uma fazenda, todas as categorias aparecem,
mesmo aquelas sem animais.

NOVIDADE v2:
- Compatível com categorias do sistema (is_system=True)
- Funciona tanto para categorias criadas via seed quanto via interface
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AnimalCategory

import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=AnimalCategory)
def create_stock_balances_for_new_category(sender, instance, created, **kwargs):
    """
    Signal: Ao criar uma nova categoria, inicializa saldos para todas as fazendas.

    Args:
        sender: Modelo AnimalCategory
        instance: Instância da categoria criada
        created: Boolean indicando se é uma nova instância
        **kwargs: Argumentos adicionais do signal
    """
    if created:
        from .models import FarmStockBalance

        count = FarmStockBalance.initialize_balances_for_category(instance)

        if count > 0:
            logger.info(
                f"[SIGNAL] Criados {count} registros de saldo "
                f"para categoria '{instance.name}' "
                f"(sistema={instance.is_system})"
            )
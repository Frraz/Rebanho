"""
Farms Signals - Automações ao criar/modificar fazendas.

REGRA DE NEGÓCIO CRÍTICA:
Quando uma nova fazenda é criada, automaticamente devem ser criados
registros de saldo (FarmStockBalance) para TODAS as categorias de
animais ativas, inicializados com quantidade = 0.

Isso garante que ao visualizar a fazenda, todas as categorias aparecem,
mesmo aquelas sem animais.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Farm


@receiver(post_save, sender=Farm)
def create_stock_balances_for_new_farm(sender, instance, created, **kwargs):
    """
    Signal: Ao criar uma nova fazenda, inicializa saldos para todas as categorias.
    
    Args:
        sender: Modelo Farm
        instance: Instância da fazenda criada
        created: Boolean indicando se é uma nova instância
        **kwargs: Argumentos adicionais do signal
    """
    if created:  # Apenas para novas fazendas
        # Import aqui para evitar circular import
        from inventory.models import FarmStockBalance
        
        # Inicializar saldos para todas as categorias ativas
        count = FarmStockBalance.initialize_balances_for_farm(instance)
        
        # Log opcional
        if count > 0:
            print(f"[SIGNAL] Criados {count} registros de saldo para fazenda '{instance.name}'")
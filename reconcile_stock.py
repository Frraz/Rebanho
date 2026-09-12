import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from inventory.models import AnimalMovement, FarmStockBalance
from farms.models import Farm
from django.db.models import Sum

print("🔄 Recalculando saldos pelo ledger...")

for farm in Farm.objects.all():
    print(f"\n📍 {farm.name}")
    for balance in FarmStockBalance.objects.filter(farm=farm):
        # Calcular saldo correto pelo ledger.
        #
        # O filtro `cancellation__isnull=True` é essencial: movimentações
        # estornadas já tiveram o saldo devolvido quando foram canceladas.
        # Contá-las de novo aqui subtraía o mesmo lote duas vezes e deixava o
        # saldo MENOR que o real — exatamente o oposto do que este script se
        # propõe a corrigir. É o mesmo filtro que os relatórios já aplicam
        # (ver reporting/services/farm_report_service.py).
        entradas = AnimalMovement.objects.filter(
            farm_stock_balance=balance,
            movement_type='ENTRADA',
            cancellation__isnull=True,
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saidas = AnimalMovement.objects.filter(
            farm_stock_balance=balance,
            movement_type='SAIDA',
            cancellation__isnull=True,
        ).aggregate(total=Sum('quantity'))['total'] or 0

        saldo_correto = entradas - saidas
        
        if balance.current_quantity != saldo_correto:
            balance.current_quantity = saldo_correto
            balance.save()
            print(f"   ✅ {balance.animal_category.name}: {balance.current_quantity} animais")

# Resumo final
print("\n" + "="*60)
total = FarmStockBalance.objects.aggregate(total=Sum('current_quantity'))['total'] or 0
print(f"📊 Total de animais no sistema: {total}")
print("="*60)

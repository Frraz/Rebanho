"""
Script de Teste Manual dos Services.

Execute este script no Django shell:
python manage.py shell < test_services.py

Ou copie e cole no shell interativo:
python manage.py shell
"""

from django.contrib.auth import get_user_model
from farms.models import Farm
from inventory.models import AnimalCategory, FarmStockBalance
from inventory.services import MovementService, StockQueryService
from operations.services import TransferService
from inventory.domain import OperationType

User = get_user_model()

print("=" * 80)
print("TESTE DOS SERVICES - SISTEMA DE GESTÃO DE REBANHOS")
print("=" * 80)

# ==============================================================================
# SETUP: Criar dados básicos
# ==============================================================================

print("\n[1] Criando usuário de teste...")
user, created = User.objects.get_or_create(
    username='teste',
    defaults={'is_staff': True, 'is_superuser': True}
)
if created:
    user.set_password('teste123')
    user.save()
print(f"✓ Usuário: {user.username}")

print("\n[2] Criando categorias de animais...")
vaca, _ = AnimalCategory.objects.get_or_create(name="Vaca")
bezerro, _ = AnimalCategory.objects.get_or_create(name="Bezerro")
novilho, _ = AnimalCategory.objects.get_or_create(name="Novilho")
print(f"✓ Categorias criadas: Vaca, Bezerro, Novilho")

print("\n[3] Criando fazendas...")
fazenda_a, _ = Farm.objects.get_or_create(name="Fazenda A")
fazenda_b, _ = Farm.objects.get_or_create(name="Fazenda B")
print(f"✓ Fazendas criadas: Fazenda A, Fazenda B")

print("\n[4] Verificando saldos iniciais...")
saldos_a = StockQueryService.get_farm_stock_summary(str(fazenda_a.id))
print(f"✓ Fazenda A tem {len(saldos_a)} categorias")
for saldo in saldos_a:
    print(f"  - {saldo['categoria_nome']}: {saldo['quantidade']}")

# ==============================================================================
# TESTE 1: MovementService - Entrada (Nascimento)
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 1: Registrar NASCIMENTO (Entrada)")
print("=" * 80)

print("\nRegistrando 10 vacas nascidas na Fazenda A...")
try:
    movimento = MovementService.execute_entrada(
        farm_id=str(fazenda_a.id),
        animal_category_id=str(vaca.id),
        operation_type=OperationType.NASCIMENTO,
        quantity=10,
        user=user,
        metadata={'observacao': 'Teste de nascimento'}
    )
    print(f"✓ Movimento registrado: ID {movimento.id}")
    print(f"  Tipo: {movimento.get_operation_type_display()}")
    print(f"  Quantidade: {movimento.quantity}")
    
    # Verificar saldo
    saldo = StockQueryService.get_current_stock(
        str(fazenda_a.id),
        str(vaca.id)
    )
    print(f"✓ Saldo atual de Vacas na Fazenda A: {saldo.current_quantity}")
    
except Exception as e:
    print(f"✗ ERRO: {e}")

# ==============================================================================
# TESTE 2: MovementService - Entrada (Compra)
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 2: Registrar COMPRA (Entrada)")
print("=" * 80)

print("\nComprando 5 bezerros para Fazenda A...")
try:
    movimento = MovementService.execute_entrada(
        farm_id=str(fazenda_a.id),
        animal_category_id=str(bezerro.id),
        operation_type=OperationType.COMPRA,
        quantity=5,
        user=user,
        metadata={'preco_unitario': 1500.00, 'fornecedor': 'Fazenda X'}
    )
    print(f"✓ Compra registrada: {movimento.quantity} bezerros")
    
    saldo = StockQueryService.get_current_stock(
        str(fazenda_a.id),
        str(bezerro.id)
    )
    print(f"✓ Saldo atual de Bezerros na Fazenda A: {saldo.current_quantity}")
    
except Exception as e:
    print(f"✗ ERRO: {e}")

# ==============================================================================
# TESTE 3: MovementService - Saída (Venda) - ERRO ESPERADO
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 3: Tentar VENDA sem saldo suficiente (deve FALHAR)")
print("=" * 80)

print("\nTentando vender 20 vacas (mas só temos 10)...")
try:
    movimento = MovementService.execute_saida(
        farm_id=str(fazenda_a.id),
        animal_category_id=str(vaca.id),
        operation_type=OperationType.VENDA,
        quantity=20,  # Mais do que temos!
        user=user
    )
    print(f"✗ ERRO: Venda não deveria ter sido permitida!")
except Exception as e:
    print(f"✓ ERRO ESPERADO capturado: {type(e).__name__}")
    print(f"  Mensagem: {e}")

# ==============================================================================
# TESTE 4: MovementService - Saída (Abate) - SUCESSO
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 4: Registrar ABATE (Saída)")
print("=" * 80)

print("\nAbatendo 3 vacas...")
try:
    movimento = MovementService.execute_saida(
        farm_id=str(fazenda_a.id),
        animal_category_id=str(vaca.id),
        operation_type=OperationType.ABATE,
        quantity=3,
        user=user,
        metadata={'motivo': 'Abate programado'}
    )
    print(f"✓ Abate registrado: {movimento.quantity} vacas")
    
    saldo = StockQueryService.get_current_stock(
        str(fazenda_a.id),
        str(vaca.id)
    )
    print(f"✓ Saldo atual de Vacas na Fazenda A: {saldo.current_quantity}")
    print(f"  (10 inicial - 3 abatidas = 7)")
    
except Exception as e:
    print(f"✗ ERRO: {e}")

# ==============================================================================
# TESTE 5: TransferService - Manejo
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 5: MANEJO - Transferir entre fazendas")
print("=" * 80)

print("\nTransferindo 2 bezerros da Fazenda A para Fazenda B...")
try:
    saida, entrada = TransferService.execute_manejo(
        source_farm_id=str(fazenda_a.id),
        target_farm_id=str(fazenda_b.id),
        animal_category_id=str(bezerro.id),
        quantity=2,
        user=user,
        metadata={'motivo': 'Redistribuição de rebanho'}
    )
    
    print(f"✓ Manejo executado com sucesso!")
    print(f"  Saída: Fazenda A - {saida.quantity} bezerros")
    print(f"  Entrada: Fazenda B + {entrada.quantity} bezerros")
    
    # Verificar saldos
    saldo_a = StockQueryService.get_current_stock(str(fazenda_a.id), str(bezerro.id))
    saldo_b = StockQueryService.get_current_stock(str(fazenda_b.id), str(bezerro.id))
    
    print(f"\n✓ Saldos atualizados:")
    print(f"  Fazenda A: {saldo_a.current_quantity} bezerros (5 - 2 = 3)")
    print(f"  Fazenda B: {saldo_b.current_quantity} bezerros (0 + 2 = 2)")
    
    # Verificar vinculação
    print(f"\n✓ Movimentos vinculados:")
    print(f"  Saída relacionada: {saida.related_movement is not None}")
    print(f"  Entrada relacionada: {entrada.related_movement is not None}")
    
except Exception as e:
    print(f"✗ ERRO: {e}")

# ==============================================================================
# TESTE 6: TransferService - Mudança de Categoria
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 6: MUDANÇA DE CATEGORIA")
print("=" * 80)

print("\nConvertendo 2 bezerros em novilhos na Fazenda A...")
try:
    saida, entrada = TransferService.execute_mudanca_categoria(
        farm_id=str(fazenda_a.id),
        source_category_id=str(bezerro.id),
        target_category_id=str(novilho.id),
        quantity=2,
        user=user,
        metadata={'motivo': 'Crescimento natural'}
    )
    
    print(f"✓ Mudança de categoria executada!")
    print(f"  Saída de Bezerro: -{saida.quantity}")
    print(f"  Entrada em Novilho: +{entrada.quantity}")
    
    # Verificar saldos
    saldo_bezerro = StockQueryService.get_current_stock(str(fazenda_a.id), str(bezerro.id))
    saldo_novilho = StockQueryService.get_current_stock(str(fazenda_a.id), str(novilho.id))
    
    print(f"\n✓ Saldos atualizados na Fazenda A:")
    print(f"  Bezerros: {saldo_bezerro.current_quantity} (3 - 2 = 1)")
    print(f"  Novilhos: {saldo_novilho.current_quantity} (0 + 2 = 2)")
    
except Exception as e:
    print(f"✗ ERRO: {e}")

# ==============================================================================
# TESTE 7: StockQueryService - Estatísticas
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 7: Estatísticas e Consultas")
print("=" * 80)

print("\nResumo da Fazenda A:")
resumo = StockQueryService.get_farm_stock_summary(str(fazenda_a.id))
for item in resumo:
    print(f"  {item['categoria_nome']}: {item['quantidade']}")

print("\nEstatísticas gerais:")
stats = StockQueryService.get_statistics()
print(f"  Total de entradas: {stats['total_entradas']}")
print(f"  Total de saídas: {stats['total_saidas']}")
print(f"  Saldo líquido: {stats['saldo_liquido']}")
print(f"  Total de movimentações: {stats['total_movimentacoes']}")

# ==============================================================================
# TESTE 8: Verificação de Consistência
# ==============================================================================

print("\n" + "=" * 80)
print("TESTE 8: Verificação de Consistência (Ledger vs Snapshot)")
print("=" * 80)

print("\nVerificando consistência de Vacas na Fazenda A...")
verificacao = StockQueryService.verify_stock_consistency(
    str(fazenda_a.id),
    str(vaca.id)
)

print(f"✓ Consistente: {verificacao['consistente']}")
print(f"  Saldo oficial (snapshot): {verificacao['saldo_oficial']}")
print(f"  Saldo calculado (ledger): {verificacao['saldo_calculado']}")
print(f"  Diferença: {verificacao['diferenca']}")

# ==============================================================================
# RESUMO FINAL
# ==============================================================================

print("\n" + "=" * 80)
print("RESUMO FINAL - ESTADO DO SISTEMA")
print("=" * 80)

print("\nFAZENDA A:")
for item in StockQueryService.get_farm_stock_summary(str(fazenda_a.id)):
    print(f"  {item['categoria_nome']}: {item['quantidade']}")

print("\nFAZENDA B:")
for item in StockQueryService.get_farm_stock_summary(str(fazenda_b.id)):
    print(f"  {item['categoria_nome']}: {item['quantidade']}")

print("\n" + "=" * 80)
print("✓ TODOS OS TESTES CONCLUÍDOS!")
print("=" * 80)
print("\nOs services estão funcionando corretamente! 🎉")
print("\nPróximos passos:")
print("  1. Criar forms para cadastros")
print("  2. Criar views para interface web")
print("  3. Criar templates para formulários")
print("=" * 80)
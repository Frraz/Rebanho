"""
Script de seed com dados realistas para o sistema de Gestão de Rebanhos.

Popula o banco com:
- 5 fazendas
- 8 categorias de animais
- 6 tipos de morte
- 15 clientes
- ~400 movimentações nos últimos 4 meses (nascimentos, compras, vendas, mortes, manejos, etc.)

Uso:
    python manage.py shell < seed_data.py
    
Ou:
    python seed_data.py
"""

import os
import sys
import django
from decimal import Decimal
from datetime import datetime, timedelta
import random

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from farms.models import Farm
from inventory.models import AnimalCategory, FarmStockBalance, AnimalMovement
from operations.models import Client, DeathReason
from inventory.domain.value_objects import OperationType, MovementType

User = get_user_model()

# ═══════════════════════════════════════════════════════════════
# CONSTANTES E DADOS BASE
# ═══════════════════════════════════════════════════════════════

FAZENDAS = [
    {"name": "Fazenda São José", "location": "Goiás"},
    {"name": "Fazenda Santa Clara", "location": "Mato Grosso"},
    {"name": "Fazenda Boa Vista", "location": "Minas Gerais"},
    {"name": "Fazenda Esperança", "location": "Mato Grosso do Sul"},
    {"name": "Fazenda Primavera", "location": "Tocantins"},
]

CATEGORIAS = [
    "Bezerro(a) 0-12 meses",
    "Novilho(a) 12-24 meses",
    "Boi/Vaca 24-36 meses",
    "Reprodutor/Matriz 36+ meses",
    "Garrote",
    "Vaca de Cria",
    "Touro Reprodutor",
    "Descarte",
]

TIPOS_MORTE = [
    "Morte Natural",
    "Acidente",
    "Doença Respiratória",
    "Verminose",
    "Botulismo",
    "Raiva",
]

CLIENTES = [
    {"name": "Frigorífico JBS", "cpf_cnpj": "61.186.888/0001-58", "phone": "(62) 3251-8000"},
    {"name": "Frigorífico Marfrig", "cpf_cnpj": "43.217.156/0001-06", "phone": "(11) 3792-8600"},
    {"name": "Fazenda do Comprador Silva", "cpf_cnpj": "123.456.789-00", "phone": "(64) 99876-5432"},
    {"name": "Leilão Nelore Premium", "cpf_cnpj": "18.765.432/0001-99", "phone": "(62) 3241-7000"},
    {"name": "Cooperativa Agropecuária Central", "cpf_cnpj": "05.234.876/0001-11", "phone": "(65) 3322-4500"},
    {"name": "João Carlos Oliveira", "cpf_cnpj": "987.654.321-00", "phone": "(62) 99123-4567"},
    {"name": "Maria Aparecida Santos", "cpf_cnpj": "456.789.123-45", "phone": "(64) 98765-4321"},
    {"name": "Agropecuária Boi Gordo Ltda", "cpf_cnpj": "22.333.444/0001-77", "phone": "(67) 3345-6789"},
    {"name": "Fazenda Recanto Feliz", "cpf_cnpj": "33.444.555/0001-88", "phone": "(62) 3456-7890"},
    {"name": "Distribuidora de Carnes do Centro-Oeste", "cpf_cnpj": "44.555.666/0001-99", "phone": "(65) 3567-8901"},
    {"name": "Pedro Henrique Almeida", "cpf_cnpj": "234.567.890-12", "phone": "(63) 99234-5678"},
    {"name": "Ana Paula Rodrigues", "cpf_cnpj": "345.678.901-23", "phone": "(62) 98345-6789"},
    {"name": "Exportadora Beef Brasil", "cpf_cnpj": "55.666.777/0001-00", "phone": "(11) 3678-9012"},
    {"name": "Leilão Virtual Top Gado", "cpf_cnpj": "66.777.888/0001-11", "phone": "(62) 3789-0123"},
    {"name": "Carlos Eduardo Ferreira", "cpf_cnpj": "567.890.123-45", "phone": "(64) 97456-7890"},
]

# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def random_date_in_last_n_days(days=120):
    """Retorna uma data aleatória nos últimos N dias."""
    start = timezone.now() - timedelta(days=days)
    random_days = random.randint(0, days)
    random_hours = random.randint(0, 23)
    random_minutes = random.randint(0, 59)
    return start + timedelta(days=random_days, hours=random_hours, minutes=random_minutes)

def peso_aleatorio(categoria_nome):
    """Retorna peso realista baseado na categoria."""
    if "Bezerro" in categoria_nome:
        return Decimal(random.randint(80, 150))
    elif "Novilho" in categoria_nome or "Garrote" in categoria_nome:
        return Decimal(random.randint(200, 350))
    elif "Boi" in categoria_nome or "Vaca" in categoria_nome:
        return Decimal(random.randint(350, 550))
    elif "Reprodutor" in categoria_nome or "Matriz" in categoria_nome or "Touro" in categoria_nome:
        return Decimal(random.randint(500, 800))
    else:
        return Decimal(random.randint(250, 450))

def preco_por_arroba():
    """Preço médio da arroba em 2024/2025."""
    return Decimal(random.uniform(220.0, 280.0)).quantize(Decimal('0.01'))

# ═══════════════════════════════════════════════════════════════
# LIMPEZA E CRIAÇÃO DE USUÁRIO ADMIN
# ═══════════════════════════════════════════════════════════════

def limpar_banco():
    """Remove todos os dados antigos (exceto superusuário)."""
    print("\n🧹 Limpando banco de dados...")
    
    AnimalMovement.objects.all().delete()
    FarmStockBalance.objects.all().delete()
    Client.objects.all().delete()
    DeathReason.objects.all().delete()
    AnimalCategory.objects.all().delete()
    Farm.objects.all().delete()
    
    print("   ✅ Banco limpo!")

def criar_usuario_admin():
    """Cria ou retorna o usuário admin para registrar as movimentações."""
    user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@rebanho.com',
            'first_name': 'Admin',
            'last_name': 'Sistema',
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        }
    )
    if created:
        user.set_password('admin123')
        user.save()
        print(f"   ✅ Superusuário criado: admin / admin123")
    else:
        print(f"   ℹ️  Superusuário já existe: {user.username}")
    
    return user

# ═══════════════════════════════════════════════════════════════
# SEED DE DADOS MESTRES
# ═══════════════════════════════════════════════════════════════

def seed_fazendas():
    """Cria fazendas."""
    print("\n🏡 Criando fazendas...")
    fazendas = []
    for data in FAZENDAS:
        fazenda, created = Farm.objects.get_or_create(
            name=data["name"],
            defaults={"location": data["location"]}
        )
        fazendas.append(fazenda)
        status = "✅ Criada" if created else "ℹ️  Já existia"
        print(f"   {status}: {fazenda.name} ({fazenda.location})")
    
    return fazendas

def seed_categorias():
    """Cria categorias de animais."""
    print("\n🐄 Criando categorias de animais...")
    categorias = []
    for nome in CATEGORIAS:
        categoria, created = AnimalCategory.objects.get_or_create(name=nome)
        categorias.append(categoria)
        status = "✅ Criada" if created else "ℹ️  Já existia"
        print(f"   {status}: {categoria.name}")
    
    return categorias

def seed_tipos_morte():
    """Cria tipos de morte."""
    print("\n💀 Criando tipos de morte...")
    tipos = []
    for nome in TIPOS_MORTE:
        tipo, created = DeathReason.objects.get_or_create(name=nome)
        tipos.append(tipo)
        status = "✅ Criado" if created else "ℹ️  Já existia"
        print(f"   {status}: {tipo.name}")
    
    return tipos

def seed_clientes():
    """Cria clientes."""
    print("\n👤 Criando clientes...")
    clientes = []
    for data in CLIENTES:
        cliente, created = Client.objects.get_or_create(
            cpf_cnpj=data["cpf_cnpj"],
            defaults={
                "name": data["name"],
                "phone": data["phone"],
            }
        )
        clientes.append(cliente)
        status = "✅ Criado" if created else "ℹ️  Já existia"
        print(f"   {status}: {cliente.name}")
    
    return clientes

# ═══════════════════════════════════════════════════════════════
# SEED DE MOVIMENTAÇÕES (O核 DO SISTEMA)
# ═══════════════════════════════════════════════════════════════

def seed_estoque_inicial(fazendas, categorias, admin_user):
    """
    Cria estoque inicial com compras fictícias há 4 meses.
    Simula que as fazendas já tinham animais antes do sistema entrar no ar.
    """
    print("\n📦 Criando estoque inicial (compras há 4 meses)...")
    
    data_inicial = timezone.now() - timedelta(days=120)
    total_movimentos = 0
    
    for fazenda in fazendas:
        for categoria in categorias:
            # Quantidade inicial varia por categoria
            if "Bezerro" in categoria.name:
                qtd = random.randint(30, 80)
            elif "Reprodutor" in categoria.name or "Touro" in categoria.name:
                qtd = random.randint(2, 5)
            elif "Matriz" in categoria.name or "Vaca de Cria" in categoria.name:
                qtd = random.randint(20, 50)
            else:
                qtd = random.randint(10, 40)
            
            if qtd > 0:
                peso = peso_aleatorio(categoria.name)
                preco_arroba = preco_por_arroba()
                arrobas = peso / 15  # 1 arroba ≈ 15kg
                preco_total = arrobas * preco_arroba * qtd
                
                AnimalMovement.objects.create(
                    farm_stock_balance=FarmStockBalance.objects.get(
                        farm=fazenda,
                        animal_category=categoria
                    ),
                    movement_type=MovementType.ENTRADA.value,
                    operation_type=OperationType.COMPRA.value,
                    quantity=qtd,
                    timestamp=data_inicial,
                    created_by=admin_user,
                    metadata={
                        "peso_medio": float(peso),
                        "preco_total": float(preco_total),
                        "nota": "Estoque inicial do sistema",
                    }
                )
                total_movimentos += 1
                print(f"   ✅ {fazenda.name} — {categoria.name}: {qtd} animais")
    
    print(f"\n   📊 Total: {total_movimentos} movimentações de estoque inicial")

def seed_nascimentos(fazendas, categorias, admin_user, num_eventos=60):
    """Cria nascimentos nos últimos 4 meses."""
    print(f"\n🐣 Criando {num_eventos} nascimentos...")
    
    bezerros = [c for c in categorias if "Bezerro" in c.name]
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(bezerros)
        qtd = random.randint(1, 8)  # Nascimentos em lote pequeno
        data = random_date_in_last_n_days(120)
        
        AnimalMovement.objects.create(
            farm_stock_balance=FarmStockBalance.objects.get(
                farm=fazenda,
                animal_category=categoria
            ),
            movement_type=MovementType.ENTRADA.value,
            operation_type=OperationType.NASCIMENTO.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={"observacao": "Nascimento natural"},
        )
    
    print(f"   ✅ {num_eventos} nascimentos registrados")

def seed_compras(fazendas, categorias, admin_user, clientes, num_eventos=25):
    """Cria compras de animais."""
    print(f"\n🛒 Criando {num_eventos} compras...")
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(categorias)
        qtd = random.randint(5, 30)
        data = random_date_in_last_n_days(120)
        peso = peso_aleatorio(categoria.name)
        preco_arroba = preco_por_arroba()
        arrobas = peso / 15
        preco_total = arrobas * preco_arroba * qtd
        
        fornecedor = random.choice(clientes)
        
        AnimalMovement.objects.create(
            farm_stock_balance=FarmStockBalance.objects.get(
                farm=fazenda,
                animal_category=categoria
            ),
            movement_type=MovementType.ENTRADA.value,
            operation_type=OperationType.COMPRA.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={
                "peso_medio": float(peso),
                "preco_total": float(preco_total),
                "fornecedor": fornecedor.name,
            }
        )
    
    print(f"   ✅ {num_eventos} compras registradas")

def seed_vendas(fazendas, categorias, admin_user, clientes, num_eventos=40):
    """Cria vendas de animais."""
    print(f"\n💰 Criando {num_eventos} vendas...")
    
    # Categorias mais vendidas (adultos)
    vendaveis = [c for c in categorias if any(x in c.name for x in ["Boi", "Vaca", "Novilho", "Garrote", "Descarte"])]
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(vendaveis)
        
        # Verificar saldo disponível
        balance = FarmStockBalance.objects.get(farm=fazenda, animal_category=categoria)
        if balance.current_quantity < 3:
            continue  # Pula se não tem estoque
        
        qtd = random.randint(3, min(balance.current_quantity, 25))
        data = random_date_in_last_n_days(100)
        peso = peso_aleatorio(categoria.name)
        preco_arroba = preco_por_arroba()
        arrobas = peso / 15
        preco_total = arrobas * preco_arroba * qtd
        
        cliente = random.choice(clientes)
        
        AnimalMovement.objects.create(
            farm_stock_balance=balance,
            movement_type=MovementType.SAIDA.value,
            operation_type=OperationType.VENDA.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={
                "cliente_id": str(cliente.id),
                "cliente_nome": cliente.name,
                "peso_medio": float(peso),
                "preco_total": float(preco_total),
            }
        )
    
    print(f"   ✅ {num_eventos} vendas registradas")

def seed_mortes(fazendas, categorias, admin_user, tipos_morte, num_eventos=15):
    """Cria registros de morte."""
    print(f"\n☠️  Criando {num_eventos} mortes...")
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(categorias)
        
        balance = FarmStockBalance.objects.get(farm=fazenda, animal_category=categoria)
        if balance.current_quantity < 1:
            continue
        
        qtd = random.randint(1, min(balance.current_quantity, 3))
        data = random_date_in_last_n_days(110)
        tipo_morte = random.choice(tipos_morte)
        
        AnimalMovement.objects.create(
            farm_stock_balance=balance,
            movement_type=MovementType.SAIDA.value,
            operation_type=OperationType.MORTE.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={
                "death_reason_id": str(tipo_morte.id),
                "death_reason_name": tipo_morte.name,
            }
        )
    
    print(f"   ✅ {num_eventos} mortes registradas")

def seed_abates(fazendas, categorias, admin_user, num_eventos=20):
    """Cria registros de abate."""
    print(f"\n🔪 Criando {num_eventos} abates...")
    
    abativeis = [c for c in categorias if any(x in c.name for x in ["Boi", "Vaca", "Descarte"])]
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(abativeis)
        
        balance = FarmStockBalance.objects.get(farm=fazenda, animal_category=categoria)
        if balance.current_quantity < 2:
            continue
        
        qtd = random.randint(2, min(balance.current_quantity, 10))
        data = random_date_in_last_n_days(100)
        peso = peso_aleatorio(categoria.name)
        
        AnimalMovement.objects.create(
            farm_stock_balance=balance,
            movement_type=MovementType.SAIDA.value,
            operation_type=OperationType.ABATE.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={
                "peso_medio": float(peso),
                "destino": "Consumo interno / Frigorífico local",
            }
        )
    
    print(f"   ✅ {num_eventos} abates registrados")

def seed_doacoes(fazendas, categorias, admin_user, clientes, num_eventos=8):
    """Cria doações."""
    print(f"\n🎁 Criando {num_eventos} doações...")
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        categoria = random.choice(categorias)
        
        balance = FarmStockBalance.objects.get(farm=fazenda, animal_category=categoria)
        if balance.current_quantity < 1:
            continue
        
        qtd = random.randint(1, min(balance.current_quantity, 5))
        data = random_date_in_last_n_days(90)
        donatario = random.choice(clientes)
        
        AnimalMovement.objects.create(
            farm_stock_balance=balance,
            movement_type=MovementType.SAIDA.value,
            operation_type=OperationType.DOACAO.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={
                "donatario": donatario.name,
                "motivo": "Doação para comunidade local",
            }
        )
    
    print(f"   ✅ {num_eventos} doações registradas")

def seed_manejos(fazendas, categorias, admin_user, num_eventos=20):
    """Cria manejos (transferências entre fazendas)."""
    print(f"\n🚚 Criando {num_eventos} manejos...")
    
    from operations.services.transfer_service import TransferService
    
    for _ in range(num_eventos):
        if len(fazendas) < 2:
            break
        
        origem = random.choice(fazendas)
        destino = random.choice([f for f in fazendas if f != origem])
        categoria = random.choice(categorias)
        
        balance_origem = FarmStockBalance.objects.get(farm=origem, animal_category=categoria)
        if balance_origem.current_quantity < 5:
            continue
        
        qtd = random.randint(3, min(balance_origem.current_quantity, 15))
        data = random_date_in_last_n_days(90)
        
        try:
            TransferService.transfer_between_farms(
                origin_farm=origem,
                destination_farm=destino,
                animal_category=categoria,
                quantity=qtd,
                user=admin_user,
                timestamp=data,
                notes=f"Manejo de {origem.name} para {destino.name}",
            )
        except Exception as e:
            print(f"   ⚠️  Erro no manejo: {e}")
            continue
    
    print(f"   ✅ {num_eventos} manejos registrados")

def seed_mudancas_categoria(fazendas, categorias, admin_user, num_eventos=30):
    """Cria mudanças de categoria (ex: bezerro vira novilho)."""
    print(f"\n🔄 Criando {num_eventos} mudanças de categoria...")
    
    from operations.services.transfer_service import TransferService
    
    # Transições realistas
    transicoes = [
        ("Bezerro(a) 0-12 meses", "Novilho(a) 12-24 meses"),
        ("Novilho(a) 12-24 meses", "Boi/Vaca 24-36 meses"),
        ("Boi/Vaca 24-36 meses", "Reprodutor/Matriz 36+ meses"),
        ("Novilho(a) 12-24 meses", "Garrote"),
        ("Boi/Vaca 24-36 meses", "Descarte"),
    ]
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        origem_nome, destino_nome = random.choice(transicoes)
        
        try:
            origem_cat = AnimalCategory.objects.get(name=origem_nome)
            destino_cat = AnimalCategory.objects.get(name=destino_nome)
        except AnimalCategory.DoesNotExist:
            continue
        
        balance_origem = FarmStockBalance.objects.get(farm=fazenda, animal_category=origem_cat)
        if balance_origem.current_quantity < 3:
            continue
        
        qtd = random.randint(2, min(balance_origem.current_quantity, 12))
        data = random_date_in_last_n_days(80)
        
        try:
            TransferService.change_category(
                farm=fazenda,
                origin_category=origem_cat,
                destination_category=destino_cat,
                quantity=qtd,
                user=admin_user,
                timestamp=data,
                notes=f"Mudança de {origem_cat.name} para {destino_cat.name}",
            )
        except Exception as e:
            print(f"   ⚠️  Erro na mudança: {e}")
            continue
    
    print(f"   ✅ {num_eventos} mudanças de categoria registradas")

def seed_desmames(fazendas, categorias, admin_user, num_eventos=25):
    """Cria desmames."""
    print(f"\n🍼 Criando {num_eventos} desmames...")
    
    bezerros = [c for c in categorias if "Bezerro" in c.name]
    
    for _ in range(num_eventos):
        fazenda = random.choice(fazendas)
        
        if not bezerros:
            continue
        
        categoria = bezerros[0]
        balance = FarmStockBalance.objects.get(farm=fazenda, animal_category=categoria)
        
        if balance.current_quantity < 3:
            continue
        
        qtd = random.randint(2, min(balance.current_quantity, 10))
        data = random_date_in_last_n_days(70)
        
        AnimalMovement.objects.create(
            farm_stock_balance=balance,
            movement_type=MovementType.ENTRADA.value,
            operation_type=OperationType.DESMAME.value,
            quantity=qtd,
            timestamp=data,
            created_by=admin_user,
            metadata={"idade_meses": random.randint(6, 8)},
        )
    
    print(f"   ✅ {num_eventos} desmames registrados")

# ═══════════════════════════════════════════════════════════════
# SCRIPT PRINCIPAL
# ═══════════════════════════════════════════════════════════════

def main():
    print("=" * 60)
    print("  🐄 SEED DE DADOS — GESTÃO DE REBANHOS")
    print("=" * 60)
    
    # 1. Limpar e preparar
    limpar_banco()
    admin_user = criar_usuario_admin()
    
    # 2. Dados mestres
    fazendas = seed_fazendas()
    categorias = seed_categorias()
    tipos_morte = seed_tipos_morte()
    clientes = seed_clientes()
    
    # Aguardar signals criarem os FarmStockBalance
    import time
    print("\n⏳ Aguardando signals criarem saldos...")
    time.sleep(2)
    
    # 3. Movimentações (ordem cronológica realista)
    seed_estoque_inicial(fazendas, categorias, admin_user)
    seed_nascimentos(fazendas, categorias, admin_user, num_eventos=60)
    seed_compras(fazendas, categorias, admin_user, clientes, num_eventos=25)
    seed_desmames(fazendas, categorias, admin_user, num_eventos=25)
    seed_mudancas_categoria(fazendas, categorias, admin_user, num_eventos=30)
    seed_manejos(fazendas, categorias, admin_user, num_eventos=20)
    seed_vendas(fazendas, categorias, admin_user, clientes, num_eventos=40)
    seed_abates(fazendas, categorias, admin_user, num_eventos=20)
    seed_mortes(fazendas, categorias, admin_user, tipos_morte, num_eventos=15)
    seed_doacoes(fazendas, categorias, admin_user, clientes, num_eventos=8)
    
    # 4. Estatísticas finais
    print("\n" + "=" * 60)
    print("  📊 RESUMO FINAL")
    print("=" * 60)
    print(f"  Fazendas:              {Farm.objects.count()}")
    print(f"  Categorias:            {AnimalCategory.objects.count()}")
    print(f"  Tipos de Morte:        {DeathReason.objects.count()}")
    print(f"  Clientes:              {Client.objects.count()}")
    print(f"  Saldos (balances):     {FarmStockBalance.objects.count()}")
    print(f"  Movimentações (total): {AnimalMovement.objects.count()}")
    print(f"  Animais no sistema:    {FarmStockBalance.objects.aggregate(total=models.Sum('current_quantity'))['total'] or 0}")
    print("=" * 60)
    print("  ✅ Seed concluído com sucesso!")
    print("=" * 60)

if __name__ == "__main__":
    from django.db import models  # Importar aqui para evitar erro no topo
    main()
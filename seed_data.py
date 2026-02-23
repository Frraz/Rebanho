"""
Script de seed com dados realistas para o sistema de Gestão de Rebanhos.
VERSÃO CORRIGIDA — usa MovementService (DDD correto)
"""

import os
import django
from decimal import Decimal
from datetime import timedelta
import random

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import models

from farms.models import Farm
from inventory.models import AnimalCategory, FarmStockBalance, AnimalMovement
from operations.models import Client, DeathReason

from inventory.domain.value_objects import OperationType
from inventory.services.movement_service import MovementService

User = get_user_model()

# ================================================================
# CONSTANTES
# ================================================================

FAZENDAS = [
    {"name": "Fazenda São José"},
    {"name": "Fazenda Santa Clara"},
    {"name": "Fazenda Boa Vista"},
    {"name": "Fazenda Esperança"},
    {"name": "Fazenda Primavera"},
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

# ================================================================
# AUXILIARES
# ================================================================

def random_date(days=120):
    base = timezone.now() - timedelta(days=days)
    return base + timedelta(
        days=random.randint(0, days),
        hours=random.randint(0, 23),
        minutes=random.randint(0, 59),
    )

def peso_aleatorio(nome):
    if "Bezerro" in nome:
        return Decimal(random.randint(80, 150))
    elif "Novilho" in nome or "Garrote" in nome:
        return Decimal(random.randint(200, 350))
    elif "Boi" in nome or "Vaca" in nome:
        return Decimal(random.randint(350, 550))
    elif "Reprodutor" in nome or "Touro" in nome:
        return Decimal(random.randint(500, 800))
    return Decimal(random.randint(250, 450))

def preco_arroba():
    return Decimal(random.uniform(220, 280)).quantize(Decimal("0.01"))

# ================================================================
# LIMPEZA
# ================================================================

def limpar_banco():
    print("\n🧹 Limpando banco...")
    AnimalMovement.objects.all().delete()
    FarmStockBalance.objects.all().delete()
    Client.objects.all().delete()
    DeathReason.objects.all().delete()
    AnimalCategory.objects.all().delete()
    Farm.objects.all().delete()
    print("   ✅ Banco limpo")

def criar_admin():
    user, _ = User.objects.get_or_create(
        username="admin",
        defaults={
            "is_staff": True,
            "is_superuser": True,
            "is_active": True,
        },
    )
    user.set_password("admin123")
    user.save()
    return user

# ================================================================
# DADOS MESTRES
# ================================================================

def seed_mestres():
    fazendas = [Farm.objects.get_or_create(name=f["name"])[0] for f in FAZENDAS]
    categorias = [AnimalCategory.objects.get_or_create(name=c)[0] for c in CATEGORIAS]
    tipos = [DeathReason.objects.get_or_create(name=t)[0] for t in TIPOS_MORTE]
    return fazendas, categorias, tipos

# ================================================================
# MOVIMENTAÇÕES (CORRIGIDAS)
# ================================================================

def seed_estoque_inicial(fazendas, categorias, user):
    print("\n📦 Estoque inicial...")

    data = timezone.now() - timedelta(days=120)

    for f in fazendas:
        for c in categorias:
            qtd = random.randint(5, 40)
            peso = peso_aleatorio(c.name)
            total = (peso / 15) * preco_arroba() * qtd

            MovementService.execute_entrada(
                farm_id=f.id,
                animal_category_id=c.id,
                operation_type=OperationType.COMPRA,
                quantity=qtd,
                user=user,
                timestamp=data,
                metadata={
                    "peso_medio": float(peso),
                    "preco_total": float(total),
                    "nota": "Estoque inicial",
                },
            )

def seed_nascimentos(fazendas, categorias, user):
    print("🐣 Nascimentos...")
    bezerros = [c for c in categorias if "Bezerro" in c.name]

    for _ in range(60):
        f = random.choice(fazendas)
        c = random.choice(bezerros)
        qtd = random.randint(1, 6)

        MovementService.execute_entrada(
            farm_id=f.id,
            animal_category_id=c.id,
            operation_type=OperationType.NASCIMENTO,
            quantity=qtd,
            user=user,
            timestamp=random_date(),
            metadata={"observacao": "Nascimento natural"},
        )

def seed_vendas(fazendas, categorias, user):
    print("💰 Vendas...")

    vendaveis = [c for c in categorias if "Boi" in c.name or "Novilho" in c.name]

    for _ in range(40):
        f = random.choice(fazendas)
        c = random.choice(vendaveis)
        balance = FarmStockBalance.objects.get(farm=f, animal_category=c)

        if balance.current_quantity < 3:
            continue

        qtd = random.randint(1, min(balance.current_quantity, 20))

        MovementService.execute_saida(
            farm_id=f.id,
            animal_category_id=c.id,
            operation_type=OperationType.VENDA,
            quantity=qtd,
            user=user,
            timestamp=random_date(),
            metadata={"nota": "Venda seed"},
        )

def seed_mortes(fazendas, categorias, tipos, user):
    print("☠️ Mortes...")

    for _ in range(15):
        f = random.choice(fazendas)
        c = random.choice(categorias)
        balance = FarmStockBalance.objects.get(farm=f, animal_category=c)

        if balance.current_quantity < 1:
            continue

        qtd = 1
        tipo = random.choice(tipos)

        MovementService.execute_saida(
            farm_id=f.id,
            animal_category_id=c.id,
            operation_type=OperationType.MORTE,
            quantity=qtd,
            user=user,
            timestamp=random_date(),
            death_reason_id=tipo.id,
        )

# ================================================================
# MAIN
# ================================================================

def main():
    print("=" * 60)
    print("🐄 SEED REBANHO — VERSÃO CORRIGIDA")
    print("=" * 60)

    limpar_banco()
    user = criar_admin()

    fazendas, categorias, tipos = seed_mestres()

    import time
    time.sleep(1)

    seed_estoque_inicial(fazendas, categorias, user)
    seed_nascimentos(fazendas, categorias, user)
    seed_vendas(fazendas, categorias, user)
    seed_mortes(fazendas, categorias, tipos, user)

    print("\n📊 RESUMO FINAL")
    print("Movimentações:", AnimalMovement.objects.count())
    print(
        "Total animais:",
        FarmStockBalance.objects.aggregate(total=models.Sum("current_quantity"))["total"] or 0,
    )
    print("✅ Seed finalizado")

if __name__ == "__main__":
    main()

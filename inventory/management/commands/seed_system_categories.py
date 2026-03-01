"""
Management Command: seed_system_categories

Cria (ou sincroniza) as 9 categorias do sistema no banco de dados.

IDEMPOTENTE: Pode ser executado múltiplas vezes sem duplicar dados.

Lógica de resolução (por categoria):
1. Busca por slug → se encontrar, atualiza campos se necessário
2. Busca por nome → se encontrar, atribui slug + marca como sistema
3. Não encontra nenhum → cria nova categoria

Isso garante compatibilidade com bancos que já têm categorias
criadas manualmente (sem slug) antes da v2.

Uso:
    python manage.py seed_system_categories
    python manage.py seed_system_categories --verbosity 2  (debug)
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from inventory.models import AnimalCategory


class Command(BaseCommand):
    help = 'Cria ou atualiza as categorias de animais do sistema (idempotente)'

    @transaction.atomic
    def handle(self, *args, **options):
        verbosity = options.get('verbosity', 1)
        created_count = 0
        updated_count = 0
        unchanged_count = 0

        self.stdout.write(
            self.style.NOTICE('Sincronizando categorias do sistema...')
        )

        for slug, name, description, order in AnimalCategory.SYSTEM_CATEGORIES:
            category = None
            created = False

            # ── Passo 1: Buscar por slug (cenário ideal)
            try:
                category = AnimalCategory.objects.get(slug=slug)
            except AnimalCategory.DoesNotExist:
                pass

            # ── Passo 2: Se não achou por slug, buscar por nome
            #    (categoria criada manualmente antes da v2)
            if category is None:
                try:
                    category = AnimalCategory.objects.get(name=name)
                    if verbosity >= 2:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Encontrada por nome: {name} '
                                f'(atribuindo slug={slug})'
                            )
                        )
                except AnimalCategory.DoesNotExist:
                    pass

            # ── Passo 3: Se não existe, criar
            if category is None:
                # Usar objects.create + update direto para evitar full_clean
                # que conflita com get_or_create do Django
                category = AnimalCategory(
                    name=name,
                    slug=slug,
                    description=description,
                    is_system=True,
                    is_active=True,
                    display_order=order,
                )
                # Bypass full_clean — salvar diretamente via super().save()
                # para evitar conflito com unique constraint durante seed
                from django.db.models import Model
                Model.save(category)
                created = True
                created_count += 1
                if verbosity >= 2:
                    self.stdout.write(
                        self.style.SUCCESS(f'  Criada: {name} (slug={slug})')
                    )
            else:
                # ── Passo 4: Atualizar campos se necessário
                updates = {}

                if category.slug != slug:
                    updates['slug'] = slug
                if category.description != description:
                    updates['description'] = description
                if category.display_order != order:
                    updates['display_order'] = order
                if not category.is_system:
                    updates['is_system'] = True
                if not category.is_active:
                    updates['is_active'] = True

                if updates:
                    # Update direto no banco (sem full_clean, sem signal)
                    AnimalCategory.objects.filter(pk=category.pk).update(**updates)
                    updated_count += 1
                    if verbosity >= 2:
                        self.stdout.write(
                            self.style.WARNING(
                                f'  Atualizada: {name} '
                                f'(campos: {list(updates.keys())})'
                            )
                        )
                else:
                    unchanged_count += 1
                    if verbosity >= 2:
                        self.stdout.write(f'  Sem alteracoes: {name}')

        # ── Inicializar saldos para todas as fazendas
        self.stdout.write(
            self.style.NOTICE('Inicializando saldos para fazendas existentes...')
        )
        from inventory.models import FarmStockBalance
        total_balances = 0
        for slug, name, _, _ in AnimalCategory.SYSTEM_CATEGORIES:
            try:
                category = AnimalCategory.objects.get(slug=slug)
                count = FarmStockBalance.initialize_balances_for_category(category)
                total_balances += count
            except AnimalCategory.DoesNotExist:
                pass

        # ── Resumo
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('Resumo da sincronizacao:'))
        self.stdout.write(f'   Criadas:        {created_count}')
        self.stdout.write(f'   Atualizadas:    {updated_count}')
        self.stdout.write(f'   Sem alteracoes: {unchanged_count}')
        self.stdout.write(f'   Saldos criados: {total_balances}')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(
            self.style.SUCCESS('Categorias do sistema sincronizadas com sucesso!')
        )
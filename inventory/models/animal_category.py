"""
Animal Category Model - Tipo/Categoria de Animal.

Representa uma classificação de animal (ex: Bezerro, Novilho, Vaca, etc.).

NOVIDADE v2: Categorias do Sistema (System Categories)
- 9 categorias pré-definidas com slug fixo para referência programática
- Campo `is_system` protege contra exclusão/desativação acidental
- Classe `WeaningRules` define mapeamento automático para desmame
- Categorias customizadas continuam funcionando normalmente (slug=None)

IMPORTANTE: Quando uma nova categoria é criada, o sistema deve garantir
que todas as fazendas existentes tenham um registro de saldo (mesmo que zero)
para essa categoria. Isso é feito via signal.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTES — Definidas FORA da classe para evitar NameError em tempo de
#              definição (classes internas não podem referenciar a classe pai)
# ══════════════════════════════════════════════════════════════════════════════

class SystemSlugs:
    """
    Identificadores programáticos das categorias fixas.

    NUNCA referencie categorias por nome ou UUID no código.
    Use sempre estas constantes:
        SystemSlugs.TOUROS
        SystemSlugs.BEZERRO_MACHO
        etc.

    Também acessível via:
        AnimalCategory.SystemSlugs.TOUROS
    """
    TOUROS = "touros"
    VACAS = "vacas"
    BEZERRO_MACHO = "bezerro-macho"
    BEZERRO_FEMEA = "bezerro-femea"
    NOVILHA_2A = "novilha-2a"
    NOVILHA_3A = "novilha-3a"
    BOIS_2A = "bois-2a"
    RUFIAO = "rufiao"
    VACA_PRIMIPARA = "vaca-primipara"


# Definição centralizada das categorias do sistema
# (slug, nome de exibição, descrição, ordem)
SYSTEM_CATEGORIES_DATA = [
    (SystemSlugs.TOUROS, "Touros", "Touros reprodutores", 1),
    (SystemSlugs.VACAS, "Vacas", "Vacas matrizes", 2),
    (SystemSlugs.BEZERRO_MACHO, "B. Macho", "Bezerros machos (até desmame)", 3),
    (SystemSlugs.BEZERRO_FEMEA, "B. Fêmea", "Bezerros fêmeas (até desmame)", 4),
    (SystemSlugs.NOVILHA_2A, "Nov. - 2A.", "Novilhas de 2 anos", 5),
    (SystemSlugs.NOVILHA_3A, "Nov. - 3A.", "Novilhas de 3 anos", 6),
    (SystemSlugs.BOIS_2A, "Bois - 2A.", "Bois de 2 anos", 7),
    (SystemSlugs.RUFIAO, "Rufião", "Rufião (boi detector de cio)", 8),
    (SystemSlugs.VACA_PRIMIPARA, "V. Primip", "Vacas primíparas (primeira cria)", 9),
]


class WeaningRules:
    """
    Regras de negócio para o processo de desmame.

    Define o mapeamento: categoria_origem → categoria_destino.
    Estas regras são a FONTE DA VERDADE para a automação do desmame.

    Uso:
        for source_slug, target_slug in WeaningRules.MAPPING.items():
            ...
    """
    # slug_origem → slug_destino
    MAPPING = {
        SystemSlugs.BEZERRO_MACHO: SystemSlugs.BOIS_2A,
        SystemSlugs.BEZERRO_FEMEA: SystemSlugs.NOVILHA_2A,
    }

    @classmethod
    def get_source_slugs(cls):
        """Retorna slugs das categorias que participam do desmame (origens)."""
        return list(cls.MAPPING.keys())

    @classmethod
    def get_target_slug(cls, source_slug: str) -> str:
        """
        Retorna o slug da categoria destino para uma origem.

        Raises:
            KeyError: Se a categoria não participa do desmame
        """
        if source_slug not in cls.MAPPING:
            raise KeyError(
                f"Categoria com slug '{source_slug}' não participa "
                f"do processo de desmame. Categorias válidas: "
                f"{list(cls.MAPPING.keys())}"
            )
        return cls.MAPPING[source_slug]

    @classmethod
    def get_display_mapping(cls):
        """
        Retorna mapeamento legível para exibição em UI.

        Returns:
            list[dict]
        """
        result = []
        categories = {
            cat.slug: cat
            for cat in AnimalCategory.objects.filter(
                slug__in=(
                    list(cls.MAPPING.keys()) + list(cls.MAPPING.values())
                )
            )
        }
        for source_slug, target_slug in cls.MAPPING.items():
            source_cat = categories.get(source_slug)
            target_cat = categories.get(target_slug)
            if source_cat and target_cat:
                result.append({
                    'source_slug': source_slug,
                    'target_slug': target_slug,
                    'source_name': source_cat.name,
                    'target_name': target_cat.name,
                    'source_id': str(source_cat.id),
                    'target_id': str(target_cat.id),
                })
        return result


# ══════════════════════════════════════════════════════════════════════════════
# MODELO
# ══════════════════════════════════════════════════════════════════════════════

class AnimalCategory(models.Model):
    """
    Categoria de Animal - Tipo/classificação de animal.

    Atributos:
        id (UUID): Identificador único universal
        name (str): Nome da categoria (único)
        slug (str): Identificador programático (único, nullable para customizadas)
        description (str): Descrição opcional
        is_system (bool): True para categorias do sistema (não podem ser excluídas)
        is_active (bool): Indica se a categoria está ativa (soft delete)
        display_order (int): Ordem de exibição nas listagens
        created_at (datetime): Data de cadastro
    """

    # Atalhos — permitem usar AnimalCategory.SystemSlugs, AnimalCategory.WeaningRules, etc.
    SystemSlugs = SystemSlugs
    WeaningRules = WeaningRules
    SYSTEM_CATEGORIES = SYSTEM_CATEGORIES_DATA

    # ══════════════════════════════════════════════════════════════════════
    # CAMPOS DO MODELO
    # ══════════════════════════════════════════════════════════════════════

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal"
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nome da Categoria",
        help_text="Nome único da categoria (ex: Bezerro, Novilho, Vaca)"
    )

    slug = models.SlugField(
        max_length=50,
        unique=True,
        null=True,
        blank=True,
        verbose_name="Slug (Identificador Programático)",
        help_text=(
            "Identificador único para referência no código. "
            "Preenchido automaticamente para categorias do sistema. "
            "Deixe em branco para categorias customizadas."
        )
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição opcional da categoria"
    )

    is_system = models.BooleanField(
        default=False,
        verbose_name="Categoria do Sistema",
        help_text=(
            "Categorias do sistema são pré-definidas e não podem "
            "ser excluídas ou ter o slug alterado."
        )
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Categorias inativas não aparecem em novas operações, mas preservam histórico"
    )

    display_order = models.IntegerField(
        default=100,
        verbose_name="Ordem de Exibição",
        help_text="Ordem de exibição nas listagens (menor = primeiro)"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Cadastro"
    )

    class Meta:
        db_table = 'animal_categories'
        verbose_name = 'Categoria de Animal'
        verbose_name_plural = 'Categorias de Animais'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['slug']),
            models.Index(fields=['is_active', 'display_order', 'name']),
            models.Index(fields=['is_system']),
        ]

    def __str__(self):
        status = " (Inativa)" if not self.is_active else ""
        system = " ⚙" if self.is_system else ""
        return f"{self.name}{status}{system}"

    def clean(self):
        """Validações de modelo"""
        super().clean()

        # Normalizar nome (remover espaços extras)
        if self.name:
            self.name = ' '.join(self.name.split())

        # Validar que nome não é vazio após normalização
        if not self.name or not self.name.strip():
            raise ValidationError({
                'name': 'Nome da categoria não pode ser vazio'
            })

        # Slug vazio → None (para não violar unique constraint)
        if self.slug is not None and self.slug.strip() == '':
            self.slug = None

        # Proteção: categorias do sistema não podem ter slug alterado
        if self.pk and self.is_system:
            try:
                original = AnimalCategory.objects.get(pk=self.pk)
                if original.is_system and original.slug != self.slug:
                    raise ValidationError({
                        'slug': (
                            'O slug de categorias do sistema não pode ser alterado. '
                            f'Slug original: {original.slug}'
                        )
                    })
            except AnimalCategory.DoesNotExist:
                pass

    def save(self, *args, **kwargs):
        """Override para garantir validação"""
        self.full_clean()
        super().save(*args, **kwargs)

    def deactivate(self):
        """
        Desativa a categoria (soft delete).

        IMPORTANTE:
        - Categorias do sistema NÃO podem ser desativadas.
        """
        if self.is_system:
            raise ValidationError(
                f"A categoria '{self.name}' é uma categoria do sistema "
                "e não pode ser desativada."
            )
        self.is_active = False
        self.save(update_fields=['is_active'])

    def activate(self):
        """Reativa uma categoria previamente desativada."""
        self.is_active = True
        self.save(update_fields=['is_active'])

    # ══════════════════════════════════════════════════════════════════════
    # MÉTODOS AUXILIARES
    # ══════════════════════════════════════════════════════════════════════

    @classmethod
    def get_by_slug(cls, slug: str) -> 'AnimalCategory':
        """Obtém categoria pelo slug de forma segura."""
        return cls.objects.get(slug=slug)

    @classmethod
    def get_weaning_categories(cls):
        """
        Retorna dict com as categorias envolvidas no desmame.

        Returns:
            dict: {
                'sources': {slug: AnimalCategory, ...},
                'targets': {slug: AnimalCategory, ...},
            }
        """
        source_slugs = cls.WeaningRules.get_source_slugs()
        target_slugs = list(cls.WeaningRules.MAPPING.values())
        all_slugs = source_slugs + target_slugs

        categories = {
            cat.slug: cat
            for cat in cls.objects.filter(slug__in=all_slugs, is_active=True)
        }

        return {
            'sources': {s: categories[s] for s in source_slugs if s in categories},
            'targets': {t: categories[t] for t in target_slugs if t in categories},
        }

    @property
    def is_weaning_source(self) -> bool:
        """Retorna True se esta categoria é origem no processo de desmame."""
        return self.slug in self.WeaningRules.MAPPING

    @property
    def weaning_target_slug(self) -> str | None:
        """Retorna o slug da categoria destino no desmame, ou None."""
        return self.WeaningRules.MAPPING.get(self.slug)
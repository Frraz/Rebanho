"""
Animal Category Model - Tipo/Categoria de Animal.

Representa uma classificação de animal (ex: Bezerro, Novilho, Vaca, etc.).
É análoga a um "SKU" ou "produto" em sistemas de estoque tradicionais.

IMPORTANTE: Quando uma nova categoria é criada, o sistema deve garantir
que todas as fazendas existentes tenham um registro de saldo (mesmo que zero)
para essa categoria. Isso é feito via signal.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class AnimalCategory(models.Model):
    """
    Categoria de Animal - Tipo/classificação de animal.
    
    Atributos:
        id (UUID): Identificador único universal
        name (str): Nome da categoria (único)
        description (str): Descrição opcional
        is_active (bool): Indica se a categoria está ativa (soft delete)
        created_at (datetime): Data de cadastro
    """
    
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
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição opcional da categoria"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Categorias inativas não aparecem em novas operações, mas preservam histórico"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Cadastro"
    )
    
    class Meta:
        db_table = 'animal_categories'
        verbose_name = 'Categoria de Animal'
        verbose_name_plural = 'Categorias de Animais'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'name']),
        ]
    
    def __str__(self):
        status = " (Inativa)" if not self.is_active else ""
        return f"{self.name}{status}"
    
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
    
    def save(self, *args, **kwargs):
        """Override para garantir validação"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def deactivate(self):
        """
        Desativa a categoria (soft delete).
        
        IMPORTANTE: Não impede visualização de histórico.
        Apenas impede novas operações com esta categoria.
        """
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def activate(self):
        """Reativa uma categoria previamente desativada."""
        self.is_active = True
        self.save(update_fields=['is_active'])
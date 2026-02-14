"""
Farm Model - Entidade Fazenda.

Representa uma unidade física de produção/criação de animais.
É análoga a um "armazém" em sistemas de estoque tradicionais.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class Farm(models.Model):
    """
    Fazenda - Unidade de localização de animais.
    
    Atributos:
        id (UUID): Identificador único universal
        name (str): Nome da fazenda (único)
        is_active (bool): Indica se a fazenda está ativa (soft delete)
        created_at (datetime): Data de cadastro
        updated_at (datetime): Data da última atualização
    """
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Identificador único universal"
    )
    
    name = models.CharField(
        max_length=200,
        unique=True,
        verbose_name="Nome da Fazenda",
        help_text="Nome único identificador da fazenda"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativa",
        help_text="Fazendas inativas não aparecem em operações, mas preservam histórico"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Cadastro"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Última Atualização"
    )
    
    class Meta:
        db_table = 'farms'
        verbose_name = 'Fazenda'
        verbose_name_plural = 'Fazendas'
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
                'name': 'Nome da fazenda não pode ser vazio'
            })
    
    def save(self, *args, **kwargs):
        """Override para garantir validação"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def deactivate(self):
        """
        Desativa a fazenda (soft delete).
        
        Nota: Não impede visualização de relatórios históricos.
        """
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def activate(self):
        """Reativa uma fazenda previamente desativada."""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
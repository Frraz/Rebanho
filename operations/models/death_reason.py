"""
Death Reason Model - Motivo/Causa de Morte.

Representa os tipos/causas de morte de animais.
Usado para rastreabilidade e análise de mortalidade.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


class DeathReason(models.Model):
    """
    Motivo de Morte - Causa da morte de animais.
    
    Atributos:
        id (UUID): Identificador único universal
        name (str): Nome do motivo (único)
        description (str): Descrição detalhada
        is_active (bool): Indica se o motivo está ativo (soft delete)
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
        verbose_name="Motivo",
        help_text="Nome do motivo da morte (ex: Doença, Predador, Natural)"
    )
    
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Descrição",
        help_text="Descrição detalhada do motivo"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Motivos inativos não aparecem em novas operações, mas preservam histórico"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data de Cadastro"
    )
    
    class Meta:
        db_table = 'death_reasons'
        verbose_name = 'Motivo de Morte'
        verbose_name_plural = 'Motivos de Morte'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_active', 'name']),
        ]
    
    def __str__(self):
        status = " (Inativo)" if not self.is_active else ""
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
                'name': 'Nome do motivo de morte não pode ser vazio'
            })
    
    def save(self, *args, **kwargs):
        """Override para garantir validação"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def deactivate(self):
        """Desativa o motivo (soft delete)"""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def activate(self):
        """Reativa um motivo previamente desativado"""
        self.is_active = True
        self.save(update_fields=['is_active'])
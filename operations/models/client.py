"""
Client Model - Cliente.

Representa clientes envolvidos em operações de venda e doação.
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


class Client(models.Model):
    """
    Cliente - Pessoa física ou jurídica que participa de transações.
    
    Atributos:
        id (UUID): Identificador único universal
        name (str): Nome do cliente
        cpf_cnpj (str): CPF ou CNPJ (opcional)
        phone (str): Telefone de contato
        email (str): Email (opcional)
        address (str): Endereço completo
        is_active (bool): Indica se o cliente está ativo (soft delete)
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
        verbose_name="Nome",
        help_text="Nome completo ou razão social do cliente"
    )
    
    cpf_cnpj = models.CharField(
        max_length=18,
        blank=True,
        null=True,
        verbose_name="CPF/CNPJ",
        help_text="CPF (000.000.000-00) ou CNPJ (00.000.000/0000-00)",
        validators=[
            RegexValidator(
                regex=r'^(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})?$',
                message="Formato inválido. Use: 000.000.000-00 (CPF) ou 00.000.000/0000-00 (CNPJ)"
            )
        ]
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Telefone",
        help_text="Telefone de contato"
    )
    
    email = models.EmailField(
        blank=True,
        null=True,
        verbose_name="Email",
        help_text="Email de contato"
    )
    
    address = models.TextField(
        blank=True,
        null=True,
        verbose_name="Endereço",
        help_text="Endereço completo do cliente"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Ativo",
        help_text="Clientes inativos não aparecem em novas operações, mas preservam histórico"
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
        db_table = 'clients'
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['cpf_cnpj']),
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
                'name': 'Nome do cliente não pode ser vazio'
            })
        
        # Remover espaços do CPF/CNPJ
        if self.cpf_cnpj:
            self.cpf_cnpj = self.cpf_cnpj.strip()
    
    def save(self, *args, **kwargs):
        """Override para garantir validação"""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def deactivate(self):
        """Desativa o cliente (soft delete)"""
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])
    
    def activate(self):
        """Reativa um cliente previamente desativado"""
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])
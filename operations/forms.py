"""
Operations Forms - Formulários de Operações.
"""
from django import forms
from django.core.exceptions import ValidationError
from operations.models import Client, DeathReason
from inventory.forms import MovementBaseForm
from .validators import validate_cpf_or_cnpj, format_cpf_or_cnpj
import re


# ==============================================================================
# FORMS DE CADASTROS
# ==============================================================================

class ClientForm(forms.ModelForm):
    """
    Formulário para criar e editar clientes.
    Aceita CPF/CNPJ com ou sem máscara e formata automaticamente.
    """
    
    class Meta:
        model = Client
        fields = ['name', 'cpf_cnpj', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'Nome completo ou razão social',
            }),
            'cpf_cnpj': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'CPF ou CNPJ',
                'data-mask': 'cpf-cnpj',  # Identificador para JS
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': '(00) 00000-0000',
                'data-mask': 'phone',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'email@exemplo.com',
            }),
            'address': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Endereço completo',
            }),
        }
        labels = {
            'name': 'Nome',
            'cpf_cnpj': 'CPF/CNPJ',
            'phone': 'Telefone',
            'email': 'Email',
            'address': 'Endereço',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # CPF/CNPJ é opcional mas se preenchido deve ser válido
        self.fields['cpf_cnpj'].required = False
        # Substituir validadores antigos do modelo
        self.fields['cpf_cnpj'].validators = [validate_cpf_or_cnpj]
        # Help text claro
        self.fields['cpf_cnpj'].help_text = 'Digite apenas os números (será formatado automaticamente)'
    
    def clean_cpf_cnpj(self):
        """
        Normaliza e formata CPF/CNPJ antes de salvar.
        Aceita com ou sem máscara e sempre salva formatado.
        """
        cpf_cnpj = self.cleaned_data.get('cpf_cnpj')
        
        if not cpf_cnpj:
            return cpf_cnpj
        
        # Formata automaticamente (adiciona pontos, traços, barra)
        formatted = format_cpf_or_cnpj(cpf_cnpj)
        
        return formatted
    
    def clean_phone(self):
        """Mantém formatação do telefone."""
        phone = self.cleaned_data.get('phone')
        if not phone:
            return phone
        
        # Deixa formatado como está (com parênteses, traço)
        return phone


class DeathReasonForm(forms.ModelForm):
    """
    Formulário para criar e editar tipos de morte.
    """
    
    class Meta:
        model = DeathReason
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'Ex: Doença, Acidente, Natural',
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Descrição opcional',
            }),
        }
        labels = {
            'name': 'Motivo',
            'description': 'Descrição',
        }


# ==============================================================================
# FORMS DE OCORRÊNCIAS
# ==============================================================================

class MorteForm(MovementBaseForm):
    """
    Formulário para registrar morte.
    Requer: tipo de morte
    """
    death_reason = forms.ModelChoiceField(
        queryset=DeathReason.objects.filter(is_active=True),
        label='Tipo de Morte',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
        })
    )


class AbateForm(MovementBaseForm):
    """
    Formulário para registrar abate.
    """
    pass


class VendaForm(MovementBaseForm):
    """
    Formulário para registrar venda.
    Requer: cliente e peso
    """
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True),
        label='Cliente',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
        })
    )
    
    # Peso é obrigatório em vendas
    peso = forms.DecimalField(
        label='Peso Total (kg)',
        required=True,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': 'Peso total em kg',
            'step': '0.01',
        })
    )
    
    preco_total = forms.DecimalField(
        label='Preço Total (R$)',
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': '0.00',
            'step': '0.01',
        })
    )


class DoacaoForm(MovementBaseForm):
    """
    Formulário para registrar doação.
    Requer: cliente (donatário)
    """
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True),
        label='Donatário',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
        }),
        help_text='Pessoa ou entidade que receberá a doação'
    )
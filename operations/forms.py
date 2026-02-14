"""
Operations Forms - Formulários de Operações.
"""
from django import forms
from django.core.exceptions import ValidationError
from operations.models import Client, DeathReason
from inventory.forms import MovementBaseForm


class ClientForm(forms.ModelForm):
    """
    Formulário para criar e editar clientes.
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
                'placeholder': '000.000.000-00 ou 00.000.000/0000-00',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': '(00) 00000-0000',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'email@example.com',
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
        help_texts = {
            'cpf_cnpj': 'CPF ou CNPJ (opcional)',
        }


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
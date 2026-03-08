"""
operations/forms.py

CORREÇÃO MRO (v3):
    Problema: VendaForm(DecimalFieldsMixin, MovementBaseForm) causava
    "Cannot create a consistent MRO" — a metaclasse do Django não suporta
    esse padrão de herança múltipla quando ambas as classes envolvem
    forms.Form na hierarquia.

    Solução: sem herança múltipla.
    - MovementBaseForm já tem clean_peso() (opcional)
    - VendaForm herda apenas MovementBaseForm e sobrescreve:
        · o campo peso (obrigatório, não opcional)
        · clean_peso() → chama _clean_decimal_required
        · clean_preco_total() → chama _clean_decimal_optional
"""
from django import forms
from django.core.exceptions import ValidationError
from operations.models import Client, DeathReason
from inventory.forms.movement_forms import (
    MovementBaseForm,
    _SELECT_CSS,
    _INPUT_CSS,
    _decimal_widget,
    _clean_decimal_optional,
    _clean_decimal_required,
)
from .validators import validate_cpf_or_cnpj, format_cpf_or_cnpj


# ══════════════════════════════════════════════════════════════════════════════
# CADASTROS
# ══════════════════════════════════════════════════════════════════════════════

class ClientForm(forms.ModelForm):
    """Formulário para criar e editar clientes."""

    class Meta:
        model = Client
        fields = ['name', 'cpf_cnpj', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': _INPUT_CSS, 'placeholder': 'Nome completo ou razão social',
            }),
            'cpf_cnpj': forms.TextInput(attrs={
                'class': _INPUT_CSS, 'placeholder': 'CPF ou CNPJ', 'data-mask': 'cpf-cnpj',
            }),
            'phone': forms.TextInput(attrs={
                'class': _INPUT_CSS, 'placeholder': '(00) 00000-0000', 'data-mask': 'phone',
            }),
            'email': forms.EmailInput(attrs={
                'class': _INPUT_CSS, 'placeholder': 'email@exemplo.com',
            }),
            'address': forms.Textarea(attrs={
                'class': _INPUT_CSS, 'rows': 3, 'placeholder': 'Endereço completo',
            }),
        }
        labels = {
            'name': 'Nome', 'cpf_cnpj': 'CPF/CNPJ',
            'phone': 'Telefone', 'email': 'Email', 'address': 'Endereço',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['cpf_cnpj'].required = False
        self.fields['cpf_cnpj'].validators = [validate_cpf_or_cnpj]
        self.fields['cpf_cnpj'].help_text = 'Digite apenas os números (será formatado automaticamente)'

    def clean_cpf_cnpj(self):
        cpf_cnpj = self.cleaned_data.get('cpf_cnpj')
        if not cpf_cnpj:
            return cpf_cnpj
        return format_cpf_or_cnpj(cpf_cnpj)

    def clean_phone(self):
        return self.cleaned_data.get('phone') or ''


class DeathReasonForm(forms.ModelForm):
    """Formulário para criar e editar tipos de morte."""

    class Meta:
        model = DeathReason
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': _INPUT_CSS, 'placeholder': 'Ex: Doença, Acidente, Natural',
            }),
            'description': forms.Textarea(attrs={
                'class': _INPUT_CSS, 'rows': 3, 'placeholder': 'Descrição opcional',
            }),
        }
        labels = {'name': 'Motivo', 'description': 'Descrição'}


# ══════════════════════════════════════════════════════════════════════════════
# OCORRÊNCIAS
# ══════════════════════════════════════════════════════════════════════════════

class MorteForm(MovementBaseForm):
    """Morte — requer tipo de morte."""
    death_reason = forms.ModelChoiceField(
        queryset=DeathReason.objects.filter(is_active=True),
        label='Tipo de Morte',
        widget=forms.Select(attrs={'class': _SELECT_CSS})
    )


class AbateForm(MovementBaseForm):
    """Abate — sem campos extras."""
    pass


class VendaForm(MovementBaseForm):
    """
    Venda — requer cliente, peso (obrigatório) e preço (opcional).

    Herança simples de MovementBaseForm — sem herança múltipla.

    Sobrescreve:
      · peso        → obrigatório (MovementBaseForm tem peso opcional)
      · clean_peso() → usa _clean_decimal_required em vez de optional
      · preco_total → campo novo, opcional
      · clean_preco_total() → _clean_decimal_optional
    """
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True),
        label='Cliente',
        widget=forms.Select(attrs={'class': _SELECT_CSS})
    )

    # Sobrescreve o peso opcional do MovementBaseForm — aqui é obrigatório
    peso = forms.CharField(
        label='Peso Total (kg)',
        required=True,
        widget=_decimal_widget('Ex: 1.250,00'),
        help_text='Peso total em kg. Formato: 1.250,80'
    )

    preco_total = forms.CharField(
        label='Preço Total (R$)',
        required=False,
        widget=_decimal_widget('Ex: 15.000,00'),
        help_text='Valor total da venda. Formato: 15.000,00'
    )

    def clean_peso(self):
        """Peso é obrigatório em vendas."""
        return _clean_decimal_required(self, 'peso')

    def clean_preco_total(self):
        """Preço é opcional."""
        return _clean_decimal_optional(self, 'preco_total')


class DoacaoForm(MovementBaseForm):
    """Doação — requer cliente (donatário)."""
    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True),
        label='Donatário',
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
        help_text='Pessoa ou entidade que receberá a doação'
    )
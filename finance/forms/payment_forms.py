"""
finance/forms/payment_forms.py

Formulários de pagamento e de ajuste manual de saldo.

Ambos são curtos de propósito: o cliente pediu um cadastro de pagamento
"bem simples", e o ajuste manual existe só para corrigir o que a operação
normal não cobre.
"""
from django import forms

from finance.models import EntryType, PaymentType
from inventory.forms.movement_forms import (
    _INPUT_CSS,
    _SELECT_CSS,
    _clean_decimal_required,
    _decimal_widget,
)
from operations.models import Client


class PaymentForm(forms.Form):
    """Data, cliente, valor, tipo e uma descrição opcional."""

    date = forms.DateField(
        label='Data do Pagamento',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'class': _INPUT_CSS, 'type': 'date'}),
        help_text='Deixe em branco para usar a data de hoje',
    )

    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True).order_by('name'),
        label='Cliente',
        widget=forms.HiddenInput(attrs={'id': 'id_client'}),
        help_text='Digite para buscar entre os clientes cadastrados',
    )

    amount = forms.CharField(
        label='Valor (R$)',
        required=True,
        widget=_decimal_widget('Ex: 5.000,00'),
    )

    payment_type = forms.ChoiceField(
        choices=PaymentType.choices,
        label='Tipo de Pagamento',
        initial=PaymentType.DINHEIRO,
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
    )

    description = forms.CharField(
        label='Descrição',
        required=False,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS,
            'rows': 2,
            'placeholder': 'Observações sobre este pagamento (opcional)',
        }),
    )

    def clean_amount(self):
        return _clean_decimal_required(self, 'amount')

    def clean_date(self):
        from datetime import date as _date

        return self.cleaned_data.get('date') or _date.today()


class AdjustmentForm(forms.Form):
    """
    Ajuste manual de saldo.

    A descrição é obrigatória aqui (diferente do pagamento): não existe
    documento de origem para consultar depois, então a explicação escrita é a
    única coisa que sobra para entender o lançamento.
    """

    date = forms.DateField(
        label='Data do Ajuste',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(attrs={'class': _INPUT_CSS, 'type': 'date'}),
        help_text='Deixe em branco para usar a data de hoje',
    )

    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True).order_by('name'),
        label='Cliente',
        widget=forms.HiddenInput(attrs={'id': 'id_client'}),
    )

    entry_type = forms.ChoiceField(
        choices=[
            (EntryType.CREDITO, 'Crédito — diminui o que o cliente deve'),
            (EntryType.DEBITO, 'Débito — aumenta o que o cliente deve'),
        ],
        label='Tipo de Ajuste',
        initial=EntryType.CREDITO,
        widget=forms.Select(attrs={'class': _SELECT_CSS}),
    )

    amount = forms.CharField(
        label='Valor (R$)',
        required=True,
        widget=_decimal_widget('Ex: 1.000,00'),
    )

    description = forms.CharField(
        label='Motivo',
        required=True,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS,
            'rows': 3,
            'placeholder': 'Explique o motivo deste ajuste. Ex: acerto combinado, '
                           'correção de lançamento antigo, perdão de dívida.',
        }),
        help_text='Obrigatório — é o único registro do porquê deste lançamento',
    )

    def clean_amount(self):
        return _clean_decimal_required(self, 'amount')

    def clean_date(self):
        from datetime import date as _date

        return self.cleaned_data.get('date') or _date.today()

    def clean_description(self):
        descricao = (self.cleaned_data.get('description') or '').strip()
        if not descricao:
            raise forms.ValidationError("Descreva o motivo do ajuste.")
        return descricao

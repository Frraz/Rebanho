"""
Movement Forms - Formulários de Movimentações.
"""
from django import forms
from django.core.exceptions import ValidationError
from inventory.models import AnimalCategory, FarmStockBalance
from farms.models import Farm


class MovementBaseForm(forms.Form):
    """
    Formulário base para movimentações.
    Contém campos comuns a todas as movimentações.
    """
    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'hx-get': '/movimentacoes/get-categories/',
            'hx-target': '#id_animal_category',
            'hx-trigger': 'change',
        })
    )
    
    animal_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Tipo de Animal',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'id': 'id_animal_category',
        })
    )
    
    quantity = forms.IntegerField(
        min_value=1,
        label='Quantidade',
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': '1',
        })
    )
    
    timestamp = forms.DateTimeField(
        label='Data/Hora',
        widget=forms.DateTimeInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'type': 'datetime-local',
        }),
        required=False,
        help_text='Deixe em branco para usar data/hora atual'
    )
    
    observacao = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'rows': 3,
            'placeholder': 'Observações adicionais (opcional)',
        })
    )
    
    peso = forms.DecimalField(
        label='Peso (kg)',
        required=False,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': 'Peso em kg (opcional)',
            'step': '0.01',
        })
    )


class NascimentoForm(MovementBaseForm):
    """Formulário para registrar nascimento"""
    pass


class DesmameForm(MovementBaseForm):
    """Formulário para registrar desmame"""
    pass


class SaldoForm(MovementBaseForm):
    """Formulário para ajuste de saldo"""
    pass


class CompraForm(MovementBaseForm):
    """Formulário para registrar compra"""
    
    preco_unitario = forms.DecimalField(
        label='Preço Unitário (R$)',
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': '0.00',
            'step': '0.01',
        })
    )
    
    fornecedor = forms.CharField(
        label='Fornecedor',
        required=False,
        max_length=200,  # CORRIGIDO: max_length ao invés de max_fields
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
            'placeholder': 'Nome do fornecedor (opcional)',
        })
    )


class ManejoForm(MovementBaseForm):
    """
    Formulário para transferência entre fazendas (Manejo).
    """
    target_farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda Destino',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        farm = cleaned_data.get('farm')
        target_farm = cleaned_data.get('target_farm')
        
        # Validar que origem e destino são diferentes
        if farm and target_farm and farm == target_farm:
            raise ValidationError(
                'A fazenda de origem e destino não podem ser iguais.'
            )
        
        return cleaned_data


class MudancaCategoriaForm(MovementBaseForm):
    """
    Formulário para mudança de categoria.
    """
    target_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Categoria Destino',
        widget=forms.Select(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('animal_category')
        target_category = cleaned_data.get('target_category')
        
        # Validar que origem e destino são diferentes
        if category and target_category and category == target_category:
            raise ValidationError(
                'A categoria de origem e destino não podem ser iguais.'
            )
        
        return cleaned_data
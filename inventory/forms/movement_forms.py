"""
Movement Forms - Formulários de Movimentações.

HTMX URLs centralizadas em /htmx/:
  /htmx/categorias-saida/   → categorias com saldo > 0
  /htmx/categorias-entrada/ → todas as categorias
  /htmx/saldo-atual/        → badge de saldo para o campo quantity
"""
from django import forms
from django.core.exceptions import ValidationError
from inventory.models import AnimalCategory, FarmStockBalance
from farms.models import Farm

# Classe CSS reutilizável para selects
_SELECT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-green-500 focus:ring-green-500 sm:text-sm'
)
_INPUT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-green-500 focus:ring-green-500 sm:text-sm'
)


class MovementBaseForm(forms.Form):
    """
    Formulário base para movimentações.
    O select de fazenda dispara HTMX para carregar categorias.
    O select de categoria dispara HTMX para mostrar saldo disponível.

    Subclasses de SAÍDA devem usar: hx_categoria_endpoint = 'categorias-saida'
    Subclasses de ENTRADA devem usar: hx_categoria_endpoint = 'categorias-entrada'
    """

    # Subclasses sobrescrevem este atributo
    hx_categoria_endpoint = 'categorias-saida'

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            # Atualiza o select de categoria ao mudar a fazenda
            'hx-get':     '/htmx/categorias-saida/',
            'hx-target':  '#id_animal_category',
            'hx-trigger': 'change',
            'hx-include': '[name="animal_category"]',
            # Também atualiza o badge de saldo
            'hx-swap':    'innerHTML',
        })
    )

    animal_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Tipo de Animal',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            'id':    'id_animal_category',
            # Atualiza o badge de saldo ao mudar a categoria
            'hx-get':     '/htmx/saldo-atual/',
            'hx-target':  '#saldo-badge',
            'hx-trigger': 'change',
            'hx-include': '[name="farm"],[name="animal_category"]',
            'hx-vals':    'js:{"farm_id": document.querySelector("[name=farm]").value, "category_id": this.value}',
        })
    )

    quantity = forms.IntegerField(
        min_value=1,
        label='Quantidade',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': '1',
            'id': 'id_quantity',
        })
    )

    timestamp = forms.DateTimeField(
        label='Data/Hora',
        widget=forms.DateTimeInput(attrs={
            'class': _INPUT_CSS,
            'type':  'datetime-local',
        }),
        required=False,
        help_text='Deixe em branco para usar a data/hora atual'
    )

    observacao = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(attrs={
            'class':       _INPUT_CSS,
            'rows':        3,
            'placeholder': 'Observações adicionais (opcional)',
        })
    )

    peso = forms.DecimalField(
        label='Peso (kg)',
        required=False,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Peso em kg (opcional)',
            'step':        '0.01',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajusta o hx-get do farm para o endpoint correto da subclasse
        endpoint = f'/htmx/{self.hx_categoria_endpoint}/'
        self.fields['farm'].widget.attrs['hx-get'] = endpoint


# ── Entradas (categorias sem filtro de saldo) ─────────────────────────────────

class NascimentoForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'


class DesmameForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'


class SaldoForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'


class CompraForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'

    preco_unitario = forms.DecimalField(
        label='Preço Unitário (R$)',
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': '0.00',
            'step':        '0.01',
        })
    )

    fornecedor = forms.CharField(
        label='Fornecedor',
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Nome do fornecedor (opcional)',
        })
    )


# ── Manejo (saída + entrada, fazendas diferentes) ─────────────────────────────

class ManejoForm(MovementBaseForm):
    """
    Farm (origem) → categorias com saldo > 0
    Target farm (destino) → não filtra categoria (já é a mesma)
    """
    hx_categoria_endpoint = 'categorias-saida'

    target_farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda Destino',
        widget=forms.Select(attrs={'class': _SELECT_CSS})
    )

    def clean(self):
        cleaned_data = super().clean()
        farm        = cleaned_data.get('farm')
        target_farm = cleaned_data.get('target_farm')
        if farm and target_farm and farm == target_farm:
            raise ValidationError('A fazenda de origem e destino não podem ser iguais.')
        return cleaned_data


# ── Mudança de Categoria (saída + entrada, fazenda igual) ─────────────────────

class MudancaCategoriaForm(MovementBaseForm):
    """
    animal_category (origem) → categorias com saldo > 0
    target_category (destino) → todas MENOS a origem

    O campo target_category usa hx-get com exclude_category para
    excluir a categoria origem do select destino dinamicamente.
    """
    hx_categoria_endpoint = 'categorias-saida'

    target_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Categoria Destino',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            'id':    'id_target_category',
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # animal_category: ao mudar, atualiza target_category excluindo a origem
        self.fields['animal_category'].widget.attrs.update({
            'hx-get':     '/htmx/categorias-entrada/',
            'hx-target':  '#id_target_category',
            'hx-trigger': 'change',
            'hx-vals':    'js:{"exclude_category": this.value}',
        })
        # Remove o hx-saldo do animal_category (já foi definido no base, sobrescreve)
        # Para mudança de categoria, o saldo fica no campo origem normalmente

    def clean(self):
        cleaned_data    = super().clean()
        category        = cleaned_data.get('animal_category')
        target_category = cleaned_data.get('target_category')
        if category and target_category and category == target_category:
            raise ValidationError('A categoria de origem e destino não podem ser iguais.')
        return cleaned_data
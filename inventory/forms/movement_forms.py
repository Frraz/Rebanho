"""
Movement Forms - Formulários de Movimentações.

HTMX URLs centralizadas em /htmx/:
  /htmx/categorias-saida/   → categorias com saldo > 0
  /htmx/categorias-entrada/ → todas as categorias
  /htmx/saldo-atual/        → badge de saldo para o campo quantity
  /htmx/saldo-desmame/      → saldos de B. Macho e B. Fêmea (novo)

NOVIDADE v2:
  - DesmameForm redesenhado com campos separados para machos e fêmeas
  - Validação de saldo no formulário
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
            'hx-get':     '/htmx/categorias-saida/',
            'hx-target':  '#id_animal_category',
            'hx-trigger': 'change',
            'hx-include': '[name="animal_category"]',
            'hx-swap':    'innerHTML',
        })
    )

    animal_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Tipo de Animal',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            'id':    'id_animal_category',
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

        self.fields['animal_category'].widget.attrs.update({
            'hx-get':     '/htmx/categorias-entrada/',
            'hx-target':  '#id_target_category',
            'hx-trigger': 'change',
            'hx-vals':    'js:{"exclude_category": this.value}',
        })

    def clean(self):
        cleaned_data    = super().clean()
        category        = cleaned_data.get('animal_category')
        target_category = cleaned_data.get('target_category')
        if category and target_category and category == target_category:
            raise ValidationError('A categoria de origem e destino não podem ser iguais.')
        return cleaned_data


# ══════════════════════════════════════════════════════════════════════════════
# DESMAME — Formulário específico com campos separados para machos e fêmeas
# ══════════════════════════════════════════════════════════════════════════════

class DesmameForm(forms.Form):
    """
    Formulário de Desmame.

    NÃO herda de MovementBaseForm porque tem UX completamente diferente:
    - Não tem seletor de categoria (categorias são fixas por regra de negócio)
    - Tem dois campos de quantidade (machos e fêmeas)
    - HTMX busca saldos de B. Macho e B. Fêmea automaticamente ao selecionar fazenda

    Fluxo HTMX:
    1. Usuário seleciona fazenda
    2. HTMX dispara GET para /htmx/saldo-desmame/?farm_id=XXX
    3. Resposta atualiza badges de saldo para B. Macho e B. Fêmea
    """

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            # Ao mudar a fazenda, atualiza os saldos disponíveis
            'hx-get':     '/htmx/saldo-desmame/',
            'hx-target':  '#desmame-saldos',
            'hx-trigger': 'change',
            'hx-swap':    'innerHTML',
        })
    )

    quantity_males = forms.IntegerField(
        min_value=0,
        initial=0,
        label='B. Macho → Bois - 2A.',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': '0',
            'id': 'id_quantity_males',
            'min': '0',
        }),
        help_text='Quantidade de bezerros machos a desmamar'
    )

    quantity_females = forms.IntegerField(
        min_value=0,
        initial=0,
        label='B. Fêmea → Nov. - 2A.',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS,
            'placeholder': '0',
            'id': 'id_quantity_females',
            'min': '0',
        }),
        help_text='Quantidade de bezerras fêmeas a desmamar'
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

    def clean(self):
        cleaned_data = super().clean()
        qty_males = cleaned_data.get('quantity_males', 0) or 0
        qty_females = cleaned_data.get('quantity_females', 0) or 0

        if qty_males == 0 and qty_females == 0:
            raise ValidationError(
                'Informe a quantidade de pelo menos uma categoria '
                '(B. Macho ou B. Fêmea) para realizar o desmame.'
            )

        return cleaned_data
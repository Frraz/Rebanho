"""
inventory/forms/movement_forms.py

Formulários de Movimentações.

CORREÇÃO MRO (v3):
    Problema anterior: DecimalFieldsMixin + MovementBaseForm causava
    "Cannot create a consistent MRO" porque a metaclasse do Django
    (DeclarativeFieldsMetaclass) não é compatível com herança múltipla
    quando ambas as bases envolvem forms.Form na cadeia.

    Solução: os clean_*() para campos decimais vivem diretamente em
    MovementBaseForm. VendaForm e CompraForm herdam normalmente e
    sobrescrevem apenas o que precisam (ex: peso obrigatório na venda).

CAMPOS DECIMAIS (peso, preço):
    Usam CharField + type="text" + data-mask="decimal" em vez de
    DecimalField + type="number". O browser aceita "1.250,80" em
    type="text"; o clean_*() normaliza para Decimal antes de salvar.
"""
from django import forms
from django.core.exceptions import ValidationError
from inventory.models import AnimalCategory, FarmStockBalance
from farms.models import Farm
from core.utils.decimal_utils import normalize_pt_br_decimal

# ── Classes CSS reutilizáveis ──────────────────────────────────────────────
_SELECT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-green-500 focus:ring-green-500 sm:text-sm'
)
_INPUT_CSS = (
    'mt-1 block w-full rounded-md border-gray-300 shadow-sm '
    'focus:border-green-500 focus:ring-green-500 sm:text-sm'
)


def _decimal_widget(placeholder='Ex: 1.250,00'):
    """
    TextInput configurado para receber decimal pt-BR via máscara JS.
    Nunca use NumberInput para campos com máscara pt-BR — o browser
    descarta a vírgula antes do valor chegar ao Django.
    """
    return forms.TextInput(attrs={
        'class':        _INPUT_CSS,
        'placeholder':  placeholder,
        'data-mask':    'decimal',   # hook para masks.js
        'inputmode':    'decimal',   # teclado numérico em mobile
        'autocomplete': 'off',
    })


def _clean_decimal_optional(form, field_name):
    """
    Normaliza um campo decimal opcional: string pt-BR → Decimal ou None.
    Chamado nos clean_*() das subclasses.
    """
    value = form.cleaned_data.get(field_name)
    if not value:
        return None
    # Se já é Decimal/float (raro), retorna direto
    if hasattr(value, 'is_integer') or hasattr(value, 'as_tuple'):
        return value
    try:
        return normalize_pt_br_decimal(str(value))
    except (ValidationError, Exception):
        raise ValidationError('Valor inválido. Use o formato 1.250,80 ou 1250,80.')


def _clean_decimal_required(form, field_name):
    """
    Normaliza um campo decimal obrigatório: string pt-BR → Decimal.
    Lança ValidationError se vazio.
    """
    value = form.cleaned_data.get(field_name)
    if not value:
        raise ValidationError('Este campo é obrigatório.')
    if hasattr(value, 'is_integer') or hasattr(value, 'as_tuple'):
        return value
    try:
        return normalize_pt_br_decimal(str(value))
    except (ValidationError, Exception):
        raise ValidationError('Valor inválido. Use o formato 1.250,80 ou 1250,80.')


# ═══════════════════════════════════════════════════════════════════════════
# FORM BASE
# ═══════════════════════════════════════════════════════════════════════════

class MovementBaseForm(forms.Form):
    """
    Base para todas as movimentações e ocorrências.

    Inclui clean_peso() que normaliza "1.250,80" → Decimal.
    Subclasses que precisam de peso obrigatório sobrescrevem clean_peso().
    """

    hx_categoria_endpoint = 'categorias-saida'

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda',
        widget=forms.Select(attrs={
            'class':      _SELECT_CSS,
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
            'class':      _SELECT_CSS,
            'id':         'id_animal_category',
            'hx-get':     '/htmx/saldo-atual/',
            'hx-target':  '#saldo-badge',
            'hx-trigger': 'change',
            'hx-include': '[name="farm"],[name="animal_category"]',
        })
    )

    quantity = forms.IntegerField(
        min_value=1,
        label='Quantidade',
        widget=forms.NumberInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': '1',
            'id':          'id_quantity',
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

    # ── Campo decimal com máscara pt-BR ──────────────────────────────────
    # CharField + type="text" — nunca NumberInput para campos com vírgula
    peso = forms.CharField(
        label='Peso (kg)',
        required=False,
        widget=_decimal_widget('Ex: 1.250,00'),
        help_text='Formato: 1.250,80'
    )

    def clean_peso(self):
        """Peso opcional — normaliza pt-BR → Decimal ou None."""
        return _clean_decimal_optional(self, 'peso')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        endpoint = f'/htmx/{self.hx_categoria_endpoint}/'
        self.fields['farm'].widget.attrs['hx-get'] = endpoint


# ═══════════════════════════════════════════════════════════════════════════
# ENTRADAS
# ═══════════════════════════════════════════════════════════════════════════

class NascimentoForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'


class SaldoForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'


class CompraForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-entrada'

    preco_unitario = forms.CharField(
        label='Preço Unitário (R$)',
        required=False,
        widget=_decimal_widget('Ex: 1.500,00'),
        help_text='Formato: 1.500,00'
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

    def clean_preco_unitario(self):
        return _clean_decimal_optional(self, 'preco_unitario')


# ═══════════════════════════════════════════════════════════════════════════
# SAÍDAS COMPOSTAS
# ═══════════════════════════════════════════════════════════════════════════

class ManejoForm(MovementBaseForm):
    hx_categoria_endpoint = 'categorias-saida'

    target_farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda Destino',
        widget=forms.Select(attrs={'class': _SELECT_CSS})
    )

    def clean(self):
        cleaned_data = super().clean()
        farm = cleaned_data.get('farm')
        target_farm = cleaned_data.get('target_farm')
        if farm and target_farm and farm == target_farm:
            raise ValidationError('A fazenda de origem e destino não podem ser iguais.')
        return cleaned_data


class MudancaCategoriaForm(MovementBaseForm):
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
        cleaned_data = super().clean()
        category = cleaned_data.get('animal_category')
        target_category = cleaned_data.get('target_category')
        if category and target_category and category == target_category:
            raise ValidationError('A categoria de origem e destino não podem ser iguais.')
        return cleaned_data


# ═══════════════════════════════════════════════════════════════════════════
# DESMAME
# ═══════════════════════════════════════════════════════════════════════════

class DesmameForm(forms.Form):
    """
    Desmame com campos separados para machos e fêmeas.
    Não herda de MovementBaseForm (UX completamente diferente).
    """

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label='Fazenda',
        widget=forms.Select(attrs={
            'class':      _SELECT_CSS,
            'hx-get':     '/htmx/saldo-desmame/',
            'hx-target':  '#desmame-saldos',
            'hx-trigger': 'change',
            'hx-swap':    'innerHTML',
        })
    )

    quantity_males = forms.IntegerField(
        min_value=0, initial=0, required=False,
        label='B. Macho → Bois - 2A.',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS, 'placeholder': '0',
            'id': 'id_quantity_males', 'min': '0',
        }),
        help_text='Quantidade de bezerros machos a desmamar'
    )

    quantity_females = forms.IntegerField(
        min_value=0, initial=0, required=False,
        label='B. Fêmea → Nov. - 2A.',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS, 'placeholder': '0',
            'id': 'id_quantity_females', 'min': '0',
        }),
        help_text='Quantidade de bezerras fêmeas a desmamar'
    )

    timestamp = forms.DateTimeField(
        label='Data/Hora',
        widget=forms.DateTimeInput(attrs={'class': _INPUT_CSS, 'type': 'datetime-local'}),
        required=False,
        help_text='Deixe em branco para usar a data/hora atual'
    )

    observacao = forms.CharField(
        label='Observação', required=False,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS, 'rows': 3,
            'placeholder': 'Observações adicionais (opcional)',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        qty_males   = cleaned_data.get('quantity_males', 0) or 0
        qty_females = cleaned_data.get('quantity_females', 0) or 0
        if qty_males == 0 and qty_females == 0:
            raise ValidationError(
                'Informe a quantidade de pelo menos uma categoria '
                '(B. Macho ou B. Fêmea) para realizar o desmame.'
            )
        return cleaned_data
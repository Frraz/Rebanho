"""
finance/forms/sale_forms.py

Formulário de venda: um cabeçalho e N lotes de animais.

Os lotes usam `formset_factory` do Django (não um formset de modelo): o
serviço é quem cria os `SaleItem`, porque cada lote também precisa gerar a
baixa de estoque. O formset aqui serve só para receber e validar os dados.

Campos decimais reusam o widget e os cleaners de
`inventory/forms/movement_forms.py` — são os mesmos do resto do sistema
(`type="text"` + máscara pt-BR, nunca `type="number"`, que descartaria a
vírgula antes do valor chegar ao Django).
"""
from django import forms
from django.core.exceptions import ValidationError

from farms.models import Farm
from inventory.forms.movement_forms import (
    _INPUT_CSS,
    _SELECT_CSS,
    _clean_decimal_optional,
    _clean_decimal_required,
    _decimal_widget,
)
from inventory.models import AnimalCategory
from operations.models import Client


class SaleForm(forms.Form):
    """Cabeçalho da venda."""

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True).order_by('name'),
        label='Fazenda',
        empty_label='Selecione a fazenda...',
        widget=forms.Select(attrs={
            'class': _SELECT_CSS,
            'id': 'id_farm',
            # O Alpine escuta esta mudança para recarregar os tipos de animal
            # disponíveis em TODAS as linhas de uma vez.
            'x-on:change': 'carregarCategorias($event.target.value)',
        }),
    )

    client = forms.ModelChoiceField(
        queryset=Client.objects.filter(is_active=True).order_by('name'),
        label='Cliente',
        widget=forms.HiddenInput(attrs={'id': 'id_client'}),
        help_text='Digite para buscar entre os clientes cadastrados',
    )

    date = forms.DateField(
        label='Data da Venda',
        required=False,
        input_formats=['%Y-%m-%d'],
        # `format='%Y-%m-%d'` é obrigatório: com USE_L10N e locale pt-BR, o
        # Django renderiza a data inicial como "12/09/2026", e um
        # <input type="date"> descarta silenciosamente o que não estiver em
        # ISO — o campo abriria vazio ao editar.
        widget=forms.DateInput(
            attrs={'class': _INPUT_CSS, 'type': 'date'}, format='%Y-%m-%d',
        ),
        help_text='Deixe em branco para usar a data de hoje',
    )

    notes = forms.CharField(
        label='Observação',
        required=False,
        widget=forms.Textarea(attrs={
            'class': _INPUT_CSS,
            'rows': 2,
            'placeholder': 'Observações sobre esta venda (opcional)',
        }),
    )

    def clean_date(self):
        """Data em branco significa hoje — mesmo comportamento das ocorrências."""
        from datetime import date as _date

        return self.cleaned_data.get('date') or _date.today()


class SaleItemForm(forms.Form):
    """
    Um lote de animais.

    O Total é calculado na tela (peso × preço/kg) mas fica editável: o usuário
    pode sobrescrever para arredondar ou registrar um valor combinado. Por isso
    o servidor aceita o que vier no campo, em vez de recalcular por cima.
    """

    # As classes `campo-*` são os ganchos que o JavaScript da tela usa para
    # achar os campos de cada linha. Não há `x-model` aqui: as linhas são
    # clonadas do formset do Django, então quem controla o estado é o DOM, e o
    # Alpine apenas lê os valores para somar e avisar sobre estoque.
    animal_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label='Tipo de Animal',
        widget=forms.Select(attrs={'class': _SELECT_CSS + ' campo-categoria'}),
    )

    quantity = forms.IntegerField(
        min_value=1,
        label='Quantidade',
        widget=forms.NumberInput(attrs={
            'class': _INPUT_CSS + ' campo-quantidade',
            'placeholder': '0',
            'min': '1',
        }),
    )

    total_weight = forms.CharField(
        label='Peso Total (kg)',
        required=True,
        widget=_decimal_widget('Ex: 9.000,00'),
        help_text='Peso somado do lote',
    )

    price_per_kg = forms.CharField(
        label='Preço por kg (R$)',
        required=False,
        widget=_decimal_widget('Ex: 10,00'),
    )

    total_amount = forms.CharField(
        label='Total (R$)',
        required=False,
        widget=_decimal_widget('Calculado'),
        help_text='Calculado, mas você pode alterar',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Marca os campos decimais para o JavaScript encontrá-los sem depender
        # do prefixo do formset, que muda a cada linha.
        for nome, classe in (
            ('total_weight', 'campo-peso'),
            ('price_per_kg', 'campo-preco-kg'),
            ('total_amount', 'campo-total'),
        ):
            widget = self.fields[nome].widget
            widget.attrs['class'] = f"{widget.attrs.get('class', '')} {classe}".strip()

    def clean_total_weight(self):
        return _clean_decimal_required(self, 'total_weight')

    def clean_price_per_kg(self):
        return _clean_decimal_optional(self, 'price_per_kg')

    def clean_total_amount(self):
        return _clean_decimal_optional(self, 'total_amount')

    def clean(self):
        cleaned = super().clean()
        peso = cleaned.get('total_weight')
        preco_kg = cleaned.get('price_per_kg')
        total = cleaned.get('total_amount')

        # Se informou o preço por quilo mas não o total, calcula o total.
        # É o caminho normal quando o JavaScript não roda (acessibilidade,
        # navegador antigo) — a conta não pode depender do front-end.
        if total is None and peso is not None and preco_kg is not None:
            from finance.models import SaleItem

            cleaned['total_amount'] = SaleItem.compute_total(peso, preco_kg)

        return cleaned


class BaseSaleItemFormSet(forms.BaseFormSet):
    """
    Garante que a venda tenha pelo menos um lote preenchido.

    A checagem de estoque NÃO é feita aqui de propósito: ela depende da
    fazenda (que vive no outro formulário) e precisa somar as quantidades da
    mesma categoria espalhadas por várias linhas. Quem faz isso é o
    SaleService, que é também quem segura o lock do saldo — duplicar a regra
    aqui só criaria duas versões dela para divergirem com o tempo.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        preenchidos = [
            form for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False)
        ]
        if not preenchidos:
            raise ValidationError(
                "Adicione pelo menos um tipo de animal à venda."
            )

    @property
    def linhas_validas(self):
        """Lotes efetivamente preenchidos, no formato que o serviço espera."""
        itens = []
        for form in self.forms:
            data = form.cleaned_data
            if not data or data.get('DELETE', False):
                continue
            if not data.get('animal_category'):
                continue
            itens.append({
                'animal_category': data['animal_category'],
                'quantity': data['quantity'],
                'total_weight': data.get('total_weight'),
                'price_per_kg': data.get('price_per_kg'),
                'total_amount': data.get('total_amount'),
            })
        return itens


SaleItemFormSet = forms.formset_factory(
    SaleItemForm,
    formset=BaseSaleItemFormSet,
    # `total_form_count` do Django é max(formulários iniciais, min_num) + extra.
    # Com min_num=1 já garantimos pelo menos 1 linha; extra=1 faria aparecer
    # 2 linhas em branco no cadastro. As demais linhas vêm só pelo botão
    # "Adicionar tipo de animal".
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)

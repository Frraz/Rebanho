"""
Inventory Forms - Formulários de Inventário.
"""

from django import forms
from django.core.exceptions import ValidationError

from farms.models import Farm
from inventory.models import AnimalCategory

# ── CSS reutilizável ──────────────────────────────────────────────────────────
_INPUT_CSS = (
    "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
    "focus:border-green-500 focus:ring-green-500 sm:text-sm"
)


class AnimalCategoryForm(forms.ModelForm):
    """Formulário para criar e editar categorias de animais."""

    class Meta:
        model = AnimalCategory
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": _INPUT_CSS,
                    "placeholder": "Ex: Vaca, Bezerro, Novilho",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": _INPUT_CSS,
                    "rows": 3,
                    "placeholder": "Descrição opcional da categoria",
                }
            ),
        }
        labels = {
            "name": "Nome da Categoria",
            "description": "Descrição",
        }

    def clean_name(self):
        """Normaliza espaços extras no nome."""
        name = self.cleaned_data.get("name")
        if name:
            name = " ".join(name.split())
        return name


class MovementBaseForm(forms.Form):
    """
    Formulário base para movimentações.
    Contém campos comuns a todas as movimentações.
    """

    farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label="Fazenda",
        widget=forms.Select(
            attrs={
                "class": _INPUT_CSS,
                "hx-get": "/movimentacoes/get-categories/",
                "hx-target": "#id_animal_category",
                "hx-trigger": "change",
            }
        ),
    )

    animal_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label="Tipo de Animal",
        widget=forms.Select(
            attrs={
                "class": _INPUT_CSS,
                "id": "id_animal_category",
            }
        ),
    )

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantidade",
        widget=forms.NumberInput(
            attrs={
                "class": _INPUT_CSS,
                "placeholder": "1",
            }
        ),
    )

    # ✅ ALTERADO: DateTimeField → DateField, datetime-local → date
    timestamp = forms.DateField(
        label="Data",
        widget=forms.DateInput(
            attrs={
                "class": _INPUT_CSS,
                "type": "date",
            }
        ),
        input_formats=["%Y-%m-%d"],
        required=False,
        help_text="Deixe em branco para usar a data atual",
    )

    observacao = forms.CharField(
        label="Observação",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": _INPUT_CSS,
                "rows": 3,
                "placeholder": "Observações adicionais (opcional)",
            }
        ),
    )

    # Peso mantido como DecimalField + NumberInput (não usa máscara pt-BR
    # neste form legado — diferente do movement_forms.py que usa CharField + máscara JS)
    peso = forms.DecimalField(
        label="Peso (kg)",
        required=False,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": _INPUT_CSS,
                "placeholder": "Peso em kg (opcional)",
                "step": "0.01",
            }
        ),
    )


class NascimentoForm(MovementBaseForm):
    """Formulário para registrar nascimento."""

    pass


class DesmameForm(MovementBaseForm):
    """Formulário para registrar desmame."""

    pass


class SaldoForm(MovementBaseForm):
    """Formulário para ajuste de saldo."""

    pass


class CompraForm(MovementBaseForm):
    """Formulário para registrar compra."""

    preco_unitario = forms.DecimalField(
        label="Preço Unitário (R$)",
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                "class": _INPUT_CSS,
                "placeholder": "0.00",
                "step": "0.01",
            }
        ),
    )

    fornecedor = forms.CharField(
        label="Fornecedor",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": _INPUT_CSS,
                "placeholder": "Nome do fornecedor (opcional)",
            }
        ),
    )


class ManejoForm(MovementBaseForm):
    """Formulário para transferência entre fazendas (Manejo)."""

    target_farm = forms.ModelChoiceField(
        queryset=Farm.objects.filter(is_active=True),
        label="Fazenda Destino",
        widget=forms.Select(attrs={"class": _INPUT_CSS}),
    )

    def clean(self):
        cleaned_data = super().clean()
        farm = cleaned_data.get("farm")
        target_farm = cleaned_data.get("target_farm")
        if farm and target_farm and farm == target_farm:
            raise ValidationError("A fazenda de origem e destino não podem ser iguais.")
        return cleaned_data


class MudancaCategoriaForm(MovementBaseForm):
    """Formulário para mudança de categoria."""

    target_category = forms.ModelChoiceField(
        queryset=AnimalCategory.objects.filter(is_active=True),
        label="Categoria Destino",
        widget=forms.Select(attrs={"class": _INPUT_CSS}),
    )

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get("animal_category")
        target_category = cleaned_data.get("target_category")
        if category and target_category and category == target_category:
            raise ValidationError(
                "A categoria de origem e destino não podem ser iguais."
            )
        return cleaned_data

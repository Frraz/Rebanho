"""
Category Forms - Formulários de Categorias de Animais.

NOVIDADE v2:
- Proteção de categorias do sistema (is_system=True)
- Campo slug bloqueado para categorias do sistema
- Campo nome bloqueado para categorias do sistema
"""
from django import forms
from django.core.exceptions import ValidationError
from inventory.models import AnimalCategory


class AnimalCategoryForm(forms.ModelForm):
    """
    Formulário para criar e editar categorias de animais.

    Categorias do sistema (is_system=True) têm nome e slug protegidos.
    """

    class Meta:
        model = AnimalCategory
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'Ex: Vaca, Bezerro, Novilho',
            }),
            'description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Descrição opcional da categoria',
            }),
        }
        labels = {
            'name': 'Nome da Categoria',
            'description': 'Descrição',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Se é uma categoria do sistema, proteger o campo nome
        if self.instance and self.instance.pk and self.instance.is_system:
            self.fields['name'].widget.attrs.update({
                'readonly': 'readonly',
                'class': (
                    'mt-1 block w-full rounded-md border-gray-200 bg-gray-100 '
                    'text-gray-500 shadow-sm sm:text-sm cursor-not-allowed'
                ),
            })
            self.fields['name'].help_text = (
                'O nome de categorias do sistema não pode ser alterado.'
            )

    def clean_name(self):
        """Normalizar e validar nome"""
        name = self.cleaned_data.get('name')
        if name:
            name = ' '.join(name.split())

        # Proteção extra: se categoria do sistema, não permitir alteração do nome
        if (
            self.instance
            and self.instance.pk
            and self.instance.is_system
            and name != self.instance.name
        ):
            raise ValidationError(
                'O nome de categorias do sistema não pode ser alterado.'
            )

        return name
"""
Category Forms - Formulários de Categorias de Animais.
"""
from django import forms
from inventory.models import AnimalCategory


class AnimalCategoryForm(forms.ModelForm):
    """
    Formulário para criar e editar categorias de animais.
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
    
    def clean_name(self):
        """Normalizar e validar nome"""
        name = self.cleaned_data.get('name')
        if name:
            name = ' '.join(name.split())
        return name
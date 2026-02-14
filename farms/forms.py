"""
Farms Forms - Formulários de Fazendas.
"""
from django import forms
from .models import Farm


class FarmForm(forms.ModelForm):
    """
    Formulário para criar e editar fazendas.
    """
    
    class Meta:
        model = Farm
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'Nome da fazenda',
            }),
        }
        labels = {
            'name': 'Nome da Fazenda',
        }
        help_texts = {
            'name': 'Nome único para identificar a fazenda',
        }
    
    def clean_name(self):
        """Normalizar e validar nome"""
        name = self.cleaned_data.get('name')
        if name:
            name = ' '.join(name.split())  # Remove espaços extras
        return name
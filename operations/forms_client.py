from django import forms
from .models import Client
from .validators import validate_cpf_or_cnpj, format_cpf_or_cnpj


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'cpf_cnpj', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'Nome completo ou razão social',
            }),
            'cpf_cnpj': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'CPF ou CNPJ',
                'data-mask': 'cpf-cnpj',  # Identificador para JS
            }),
            'phone': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': '(00) 00000-0000',
                'data-mask': 'phone',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'placeholder': 'email@exemplo.com',
            }),
            'address': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-green-500 focus:ring-green-500 sm:text-sm',
                'rows': 3,
                'placeholder': 'Endereço completo',
            }),
        }
        help_texts = {
            'cpf_cnpj': 'Digite apenas números ou com máscara (ex: 000.000.000-00 ou 00.000.000/0001-00)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # CPF/CNPJ é opcional mas se preenchido deve ser válido
        self.fields['cpf_cnpj'].required = False
        self.fields['cpf_cnpj'].validators.append(validate_cpf_or_cnpj)
    
    def clean_cpf_cnpj(self):
        """
        Normaliza e formata CPF/CNPJ antes de salvar.
        Aceita com ou sem máscara e sempre salva formatado.
        """
        cpf_cnpj = self.cleaned_data.get('cpf_cnpj')
        
        if not cpf_cnpj:
            return cpf_cnpj
        
        # Formata automaticamente (adiciona pontos, traços, barra)
        formatted = format_cpf_or_cnpj(cpf_cnpj)
        
        return formatted
    
    def clean_phone(self):
        """Remove formatação do telefone se necessário."""
        phone = self.cleaned_data.get('phone')
        if not phone:
            return phone
        
        # Pode opcionalmente remover formatação:
        # import re
        # return re.sub(r'\D', '', phone)
        
        # Ou deixar formatado como está
        return phone
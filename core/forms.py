"""
Core Forms — Formulário de cadastro de usuário.

Regras de negócio:
  - Usuário criado com is_active=False
  - Admin precisa ativar via /admin/ ou painel
  - Senha confirmada no formulário
  - Username único validado no form (mensagem amigável)
  - E-mail único validado no form
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

_INPUT_CSS = (
    'w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm '
    'focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-green-500'
)


class RegisterForm(forms.ModelForm):
    """
    Formulário de cadastro público.
    Cria usuário inativo — admin precisa ativar.
    """
    first_name = forms.CharField(
        label='Nome',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Seu nome completo',
            'autofocus':   True,
        })
    )

    last_name = forms.CharField(
        label='Sobrenome',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Sobrenome (opcional)',
        })
    )

    email = forms.EmailField(
        label='E-mail',
        widget=forms.EmailInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'seu@email.com',
        })
    )

    username = forms.CharField(
        label='Nome de usuário',
        max_length=150,
        widget=forms.TextInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'ex: joao.silva',
        }),
        help_text='Somente letras, números e os caracteres @/./+/-/_'
    )

    password1 = forms.CharField(
        label='Senha',
        widget=forms.PasswordInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Mínimo 8 caracteres',
        })
    )

    password2 = forms.CharField(
        label='Confirmar senha',
        widget=forms.PasswordInput(attrs={
            'class':       _INPUT_CSS,
            'placeholder': 'Repita a senha',
        })
    )

    class Meta:
        model  = User
        fields = ['first_name', 'last_name', 'email', 'username']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError('Este nome de usuário já está em uso. Escolha outro.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean_password1(self):
        password = self.cleaned_data.get('password1')
        if password:
            try:
                validate_password(password)
            except ValidationError as e:
                raise ValidationError(list(e.messages))
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'As senhas não conferem.')
        return cleaned_data

    def save(self, commit=True):
        """
        Salva usuário com is_active=False.
        Admin precisa ativar em /admin/ ou via painel.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_active = False  # ← CHAVE: inativo até aprovação do admin
        if commit:
            user.save()
        return user
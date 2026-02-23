"""
Validadores customizados para CPF e CNPJ.
Aceita com ou sem máscara e valida o dígito verificador.
"""

from django.core.exceptions import ValidationError
import re


def validate_cpf(value):
    """
    Valida CPF com ou sem máscara.
    Aceita: 062.606.522-40 ou 06260652240
    """
    # Remove tudo que não é número
    cpf = re.sub(r'\D', '', value)
    
    # Verifica se tem 11 dígitos
    if len(cpf) != 11:
        raise ValidationError('CPF deve ter 11 dígitos.')
    
    # Verifica se não é uma sequência de números iguais
    if cpf == cpf[0] * 11:
        raise ValidationError('CPF inválido.')
    
    # Validação do primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[9]) != digito1:
        raise ValidationError('CPF inválido.')
    
    # Validação do segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    if int(cpf[10]) != digito2:
        raise ValidationError('CPF inválido.')


def validate_cnpj(value):
    """
    Valida CNPJ com ou sem máscara.
    Aceita: 79.527.120/0001-00 ou 79527120000100
    """
    # Remove tudo que não é número
    cnpj = re.sub(r'\D', '', value)
    
    # Verifica se tem 14 dígitos
    if len(cnpj) != 14:
        raise ValidationError('CNPJ deve ter 14 dígitos.')
    
    # Verifica se não é uma sequência de números iguais
    if cnpj == cnpj[0] * 14:
        raise ValidationError('CNPJ inválido.')
    
    # Validação do primeiro dígito verificador
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    resto = soma % 11
    digito1 = 0 if resto < 2 else 11 - resto
    
    if int(cnpj[12]) != digito1:
        raise ValidationError('CNPJ inválido.')
    
    # Validação do segundo dígito verificador
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    resto = soma % 11
    digito2 = 0 if resto < 2 else 11 - resto
    
    if int(cnpj[13]) != digito2:
        raise ValidationError('CNPJ inválido.')


def validate_cpf_or_cnpj(value):
    """
    Valida CPF ou CNPJ automaticamente baseado no tamanho.
    """
    if not value:
        return  # Campo opcional
    
    # Remove tudo que não é número
    numbers = re.sub(r'\D', '', value)
    
    if len(numbers) == 11:
        validate_cpf(value)
    elif len(numbers) == 14:
        validate_cnpj(value)
    else:
        raise ValidationError('Digite um CPF (11 dígitos) ou CNPJ (14 dígitos) válido.')


def format_cpf(cpf):
    """Formata CPF: 06260652240 -> 062.606.522-40"""
    cpf = re.sub(r'\D', '', cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"


def format_cnpj(cnpj):
    """Formata CNPJ: 79527120000100 -> 79.527.120/0001-00"""
    cnpj = re.sub(r'\D', '', cnpj)
    if len(cnpj) != 14:
        return cnpj
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"


def format_cpf_or_cnpj(value):
    """Formata CPF ou CNPJ automaticamente."""
    if not value:
        return value
    
    numbers = re.sub(r'\D', '', value)
    
    if len(numbers) == 11:
        return format_cpf(numbers)
    elif len(numbers) == 14:
        return format_cnpj(numbers)
    else:
        return value  # Retorna sem formatação se inválido
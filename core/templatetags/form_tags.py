from django import template

register = template.Library()

@register.filter
def getattribute(obj, attr):
    """Get attribute from object"""
    return getattr(obj, attr, None)

@register.filter
def fieldtype(field):
    """Get field type"""
    return field.field.__class__.__name__

@register.filter
def selected_model_choice(field):
    """
    Para um BoundField de ModelChoiceField: devolve a instância atualmente
    selecionada (pelo valor enviado/inicial), ou None.

    Usado para re-preencher a caixa de busca do client_picker com o nome do
    cliente já escolhido, tanto ao editar quanto ao reexibir um formulário
    que falhou na validação.
    """
    valor = field.value()
    if not valor:
        return None
    try:
        return field.field.queryset.filter(pk=valor).first()
    except (ValueError, TypeError):
        return None
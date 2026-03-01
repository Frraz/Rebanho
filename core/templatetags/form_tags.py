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
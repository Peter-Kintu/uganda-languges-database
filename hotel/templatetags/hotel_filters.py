# hotel/templatetags/hotel_filters.py
from django import template

register = template.Library()

@register.filter(name='split')
def split(value, key):
    """
    Returns the value turned into a list by splitting it by the key.
    """
    return value.split(key)
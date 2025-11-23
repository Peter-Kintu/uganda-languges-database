from django import template
from django.forms import BoundField

# The template.Library instance is used to register all custom tags and filters.
register = template.Library()

@register.filter
def split(value, arg):
    """
    Splits a string by the given argument (delimiter) and returns a list.
    Used for iterating over comma-separated strings in the template.
    Usage: {% for field_name in 'first_name,last_name'|split:',' %}
    """
    if isinstance(value, str):
        return value.split(arg)
    return []

@register.filter
def get_field(form, field_name):
    """
    Dynamically retrieves a form field (BoundField) by its string name.
    Used to access form fields within the loop.
    Usage: {% with form|get_field:field_name as field %}
    """
    # Check if the form has a 'fields' attribute and if the field_name exists
    if hasattr(form, 'fields') and field_name in form.fields:
        # Access the field using dictionary-like lookup on the form
        # This returns the necessary BoundField object
        return form[field_name]
    return None
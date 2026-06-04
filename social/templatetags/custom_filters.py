from django import template

register = template.Library()


@register.filter
def replace(value, arg):
    """
    Replace first argument with second argument in the string.
    Uses pipe (|) as separator to avoid Django template parsing issues with colons.
    Usage: {{ value|replace:'search|replace' }}
    Example: {{ url|replace:'http://|https://' }}
    """
    if not arg:
        return value
    
    # Split the argument by pipe to get search and replace strings
    parts = arg.split('|')
    if len(parts) != 2:
        return value
    
    search, replacement = parts
    return str(value).replace(search, replacement)

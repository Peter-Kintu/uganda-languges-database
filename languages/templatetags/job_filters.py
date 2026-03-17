from django import template

register = template.Library()

@register.filter
def add_publisher(url, publisher_id):
    if '?' in url:
        return f"{url}&publisher={publisher_id}"
    else:
        return f"{url}?publisher={publisher_id}"
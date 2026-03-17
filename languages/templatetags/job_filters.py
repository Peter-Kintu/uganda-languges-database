from django import template

register = template.Library()

@register.filter
def add_publisher(url, publisher_id):
    if not url:
        return url
    if not publisher_id or str(publisher_id).lower() in ('none', ''):
        return url  # return raw URL rather than appending ?publisher=None
    if '?' in url:
        return f"{url}&publisher={publisher_id}"
    else:
        return f"{url}?publisher={publisher_id}"
from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'price',
        'is_negotiable',
        'language_tag',
        'whatsapp_number',
        'slug',
    )
    list_filter = ('language_tag', 'is_negotiable')
    search_fields = ('name', 'description', 'language_tag', 'whatsapp_number')
    prepopulated_fields = {'slug': ('name',)}
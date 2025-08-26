from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'vendor_name',  # Added vendor name to list display
        'price',
        'is_negotiable',
        'language_tag',
        'whatsapp_number',
        'slug',
    )
    list_filter = ('language_tag', 'is_negotiable')
    search_fields = ('name', 'description', 'vendor_name', 'language_tag', 'whatsapp_number')
    prepopulated_fields = {'slug': ('name',)}
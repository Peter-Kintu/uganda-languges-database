from django.contrib import admin
from django.urls import path
from .models import Product
from .views import export_products_json

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'vendor_name',
        'price',
        'is_negotiable',
        'language_tag',
        'whatsapp_number',
        'tiktok_url',
        'slug',
    )
    list_filter = ('language_tag', 'is_negotiable')
    search_fields = ('name', 'description', 'vendor_name', 'language_tag', 'whatsapp_number')
    prepopulated_fields = {'slug': ('name',)}
    list_select_related = ()
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-json/', self.admin_site.admin_view(export_products_json), name='eshop_product_export_json'),
        ]
        return custom_urls + urls
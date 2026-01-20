from django.contrib import admin
from django.urls import path
from .models import Product
from .views import export_products_json, sync_aliexpress_products

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # This line requires the HTML file to exist in your templates folder
    change_list_template = "admin/eshop/product_change_list.html" 
    
    list_display = (
        'name',
        'vendor_name',
        'price',
        'is_negotiable',
        'country',
        'whatsapp_number',
        'tiktok_url',
        'slug',
    )
    list_filter = ('country', 'is_negotiable')
    search_fields = ('name', 'description', 'vendor_name', 'country', 'whatsapp_number')
    prepopulated_fields = {'slug': ('name',)}
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('export-json/', self.admin_site.admin_view(export_products_json), name='eshop_product_export_json'),
            path('sync-aliexpress/', self.admin_site.admin_view(sync_aliexpress_products), name='sync_aliexpress_admin'),
        ]
        return custom_urls + urls
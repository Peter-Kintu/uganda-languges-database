from django.contrib import admin
from django.urls import path
from .models import Product
from .views import export_products_json, sync_aliexpress_products

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # We are keeping all your fields since you confirmed they were working before
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
    
    list_select_related = [] 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # 1. We change the internal path to 'sync-now' to avoid clashing with the storefront
            # 2. We change the name to 'sync_aliexpress_admin_unique'
            path('sync-now/', self.admin_site.admin_view(sync_aliexpress_products), name='sync_aliexpress_admin_unique'),
            
            path('export-json/', self.admin_site.admin_view(export_products_json), name='eshop_product_export_json'),
        ]
        return custom_urls + urls
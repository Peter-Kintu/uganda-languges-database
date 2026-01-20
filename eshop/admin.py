from django.contrib import admin
from django.urls import path
from .models import Product
from .views import export_products_json, sync_aliexpress_products

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # --- CRITICAL FIX ---
    # We ensure no custom templates are called to prevent Koyeb crashes.
    # We also simplified list_display to only core fields to find the error.
    
    list_display = (
        'name',
        'vendor_name',
        'price',
        'country',
        'whatsapp_number',
        'slug',
    )
    
    # If 'tiktok_url' is definitely in your models.py, you can uncomment it below:
    # list_display += ('tiktok_url',)

    list_filter = ('country', 'is_negotiable')
    search_fields = ('name', 'description', 'vendor_name', 'country', 'whatsapp_number')
    prepopulated_fields = {'slug': ('name',)}
    
    # Performance optimization for foreign keys (if any)
    list_select_related = [] 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # URL for JSON export
            path('export-json/', self.admin_site.admin_view(export_products_json), name='eshop_product_export_json'),
            
            # URL for the Sync Button (Linked in your Jazzmin settings)
            path('sync-aliexpress/', self.admin_site.admin_view(sync_aliexpress_products), name='sync_aliexpress_admin'),
        ]
        return custom_urls + urls
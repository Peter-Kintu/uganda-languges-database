from django.contrib import admin
from django.urls import path
from .models import Product
from .views import export_products_json, sync_aliexpress_products

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # Keeping all original fields as they are verified to work with your model
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
    
    # Ensures efficient loading for the admin list view
    list_select_related = [] 

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            # 1. Path changed to 'sync-now/' to avoid clashing with the 'eshop/sync-aliexpress/' storefront URL
            # 2. Name set to 'sync_aliexpress_admin_unique' to avoid reverse lookup conflicts in production
            path(
                'sync-now/', 
                self.admin_site.admin_view(sync_aliexpress_products), 
                name='sync_aliexpress_admin_unique'
            ),
            
            # 3. Dedicated path for JSON export
            path(
                'export-json/', 
                self.admin_site.admin_view(export_products_json), 
                name='eshop_product_export_json'
            ),
        ]
        return custom_urls + urls
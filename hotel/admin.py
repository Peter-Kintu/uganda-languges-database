from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages
from .models import Accommodation
from .views import sync_hotels_travelpayouts  # Import the function we updated in views.py

@admin.register(Accommodation)
class AccommodationAdmin(admin.ModelAdmin):
    # What columns to show in the admin list
    # UPDATED: Added owner, verification status, and lat/lon visibility
    list_display = ('name', 'city', 'country', 'source', 'is_verified_vendor', 'owner', 'stars', 'price_per_night')
    
    # Sidebar filters
    # UPDATED: Filter by verification and owner
    list_filter = ('country', 'source', 'is_verified_vendor', 'stars')
    
    # Search box functionality
    search_fields = ('name', 'city', 'country', 'owner__username')
    
    # Allows you to verify vendors directly from the list view
    list_editable = ('is_verified_vendor',)

    # Prepopulated fields for manual entry
    prepopulated_fields = {'slug': ('name', 'city')}

    # World-class organization of the detail page
    fieldsets = (
        ('General Information', {
            'fields': ('name', 'slug', 'description', 'source', 'external_id')
        }),
        ('Vendor & Ecosystem', {
            'fields': ('owner', 'is_verified_vendor')
        }),
        ('Geography & GPS (5KM Engine)', {
            'fields': ('country', 'city', 'address', 'latitude', 'longitude')
        }),
        ('Pricing & Rating', {
            'fields': ('price_per_night', 'currency', 'stars')
        }),
        ('Media & Social', {
            'fields': ('image', 'image_url', 'whatsapp_number', 'tiktok_url', 'affiliate_url')
        }),
    )

    def get_urls(self):
        """
        Adds a custom URL pattern for the sync action.
        This allows the URL /admin/hotel/accommodation/sync/ to work.
        """
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync/', 
                self.admin_site.admin_view(self.run_sync), 
                name='hotel_accommodation_sync'
            ),
        ]
        return custom_urls + urls

    def run_sync(self, request):
        """
        A wrapper method that calls the logic in views.py and redirects
        the user back to the list of hotels in the admin.
        """
        try:
            # We call the view function directly
            sync_hotels_travelpayouts(request)
        except Exception as e:
            self.message_user(request, f"Critical Admin Error: {str(e)}", level=messages.ERROR)
        
        # Always return to the admin list view (the 'changelist')
        return redirect("admin:hotel_accommodation_changelist")
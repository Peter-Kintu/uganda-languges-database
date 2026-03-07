from django.contrib import admin
from .models import Movie, Order

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    # Added 'category' to the list display to help manage 'Date Night' vs 'Trending' tags
    list_display = ('name', 'category', 'genre', 'rating', 'view_count', 'source_display')
    
    # Added 'category' and 'release_date' filters for easier catalog management
    list_filter = ('category', 'genre', 'rating', 'release_date')
    
    # Search by title or AI keywords
    search_fields = ('name', 'ai_recommendation_tags', 'description')
    
    # Automatically generates the URL slug as you type the name
    prepopulated_fields = {'slug': ('name',)}
    
    # Organized layout for adding/editing movies
    fieldsets = (
        ('Movie Identity', {
            'fields': ('name', 'slug', 'category', 'genre', 'rating', 'release_date')
        }),
        ('AI & Recommendations', {
            'fields': ('ai_summary', 'ai_recommendation_tags', 'description')
        }),
        ('Monetization (Affiliate)', {
            'fields': ('image_url', 'trailer_url', 'affiliate_url', 'price'),
            'description': 'Enter your unique tracking links from Amazon, Netflix, or Disney+ here.'
        }),
        ('Performance Stats', {
            'fields': ('view_count',),
            'classes': ('collapse',)  # Keeps stats hidden unless clicked
        }),
    )

    def source_display(self, obj):
        """Custom column to show if AI generated the description."""
        return "✨ AI Enhanced" if obj.ai_summary else "👤 Manual Entry"
    source_display.short_description = 'Content Source'

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin view for tracking affiliate click-throughs."""
    list_display = ('buyer', 'movie', 'total_amount', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('buyer__username', 'movie__name')
    readonly_fields = ('created_at',)
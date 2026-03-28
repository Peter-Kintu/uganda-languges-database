from django.contrib import admin
from django import forms
from .models import SocialProfile, BusinessReel, VideoEndorsement

# --- CUSTOM WIDGETS/FORMS ---

class SocialProfileAdminForm(forms.ModelForm):
    """
    Custom form to provide a better UI for the Bento JSON configuration.
    """
    class Meta:
        model = SocialProfile
        fields = '__all__'
        widgets = {
            'bento_config': forms.Textarea(attrs={
                'rows': 10, 
                'cols': 80, 
                'placeholder': '{"layout": "grid", "items": [{"id": "trust", "size": "small"}]}',
                'class': 'vLargeTextField'
            }),
        }

# --- ADMIN CLASSES ---

@admin.register(SocialProfile)
class SocialProfileAdmin(admin.ModelAdmin):
    form = SocialProfileAdminForm
    list_display = ('user', 'trust_score_display', 'verified_deals_count', 'is_verified_merchant', 'auto_negotiation_enabled')
    list_filter = ('is_verified_merchant', 'auto_negotiation_enabled')
    search_fields = ('user__username', 'user__email')
    
    fieldsets = (
        ('User Identity', {
            'fields': ('user',)
        }),
        ('Pillar 1: Trust Ledger', {
            'fields': ('trust_score', 'verified_deals_count', 'is_verified_merchant'),
            'description': "Verified metrics that power the 'Proof of Work' profile layer."
        }),
        ('Pillar 3: Agentic Commerce', {
            'fields': ('auto_negotiation_enabled', 'minimum_margin_percent'),
            'description': "Global AI Negotiator limits for this professional."
        }),
        ('Pillar 4: UI Configuration', {
            'fields': ('bento_config',),
            'classes': ('collapse',),
            'description': "Bento Grid layout settings for the modern profile view."
        }),
    )

    def trust_score_display(self, obj):
        return f"{obj.trust_score}%"
    trust_score_display.short_description = 'Trust Score'


@admin.register(BusinessReel)
class BusinessReelAdmin(admin.ModelAdmin):
    """
    Command center for shoppable reels. Monitor speed and negotiation floors.
    """
    list_display = ('caption_summary', 'author', 'price_display', 'floor_display', 'is_low_bandwidth_optimized', 'created_at')
    list_filter = ('currency', 'is_low_bandwidth_optimized', 'created_at')
    search_fields = ('author__username', 'caption')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Content', {
            'fields': ('author', 'video', 'thumbnail', 'caption')
        }),
        ('Pillar 3: Agentic Pricing', {
            'fields': ('price', 'currency', 'floor_price'),
            'description': "Set the listing price and the private AI negotiation floor."
        }),
        ('Pillar 2: Performance', {
            'fields': ('is_low_bandwidth_optimized', 'created_at'),
            'description': "Optimization status for low-latency delivery across Africa."
        }),
    )

    def caption_summary(self, obj):
        return obj.caption[:50] + "..." if len(obj.caption) > 50 else obj.caption
    caption_summary.short_description = 'Caption'

    def price_display(self, obj):
        return f"{obj.currency} {obj.price:,}"
    price_display.short_description = 'Public Price'

    def floor_display(self, obj):
        floor = obj.get_negotiation_floor()
        return f"{obj.currency} {floor:,.2f}"
    floor_display.short_description = 'AI Floor'


@admin.register(VideoEndorsement)
class VideoEndorsementAdmin(admin.ModelAdmin):
    """
    Manage the 'Verified Proof' (Pillar 1) video testimonials.
    """
    list_display = ('professional', 'client', 'is_verified_transaction', 'created_at')
    list_filter = ('is_verified_transaction', 'created_at')
    search_fields = ('professional__username', 'client__username')
    readonly_fields = ('created_at',)
    
    fieldsets = (
        ('Endorsement Details', {
            'fields': ('professional', 'client', 'video_clip', 'is_verified_transaction', 'created_at')
        }),
    )
from django.contrib import admin
from django import forms
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.urls import path, reverse
from django.utils.html import format_html
from .models import (
    SocialProfile,
    MerchantIdentityVerification,
    BusinessReel,
    VideoEndorsement,
    SecureMessage,
)

# --- CUSTOM WIDGETS/FORMS ---

class SocialProfileAdminForm(forms.ModelForm):
    """
    Pillar 4: Bento Configuration Form.
    Provides a cleaner UI for editing the profile JSON grid layout.
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
    list_display = (
        'user', 
        'trust_score_display', 
        'verified_deals_count', 
        'is_verified_merchant', 
        'verification_tier',
        'verification_status',
        'auto_negotiation_enabled'
    )
    list_filter = ('is_verified_merchant', 'verification_tier', 'verification_status', 'auto_negotiation_enabled')
    search_fields = ('user__username', 'user__email')
    actions = ['recalculate_trust']
    
    fieldsets = (
        ('User Identity', {
            'fields': ('user',)
        }),
        ('Pillar 1: Trust Ledger', {
            'fields': ('trust_score', 'verified_deals_count', 'is_verified_merchant', 'verification_tier', 'verification_status', 'business_registration_ref'),
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

    @admin.action(description="Recalculate selected Trust Scores")
    def recalculate_trust(self, request, queryset):
        for profile in queryset:
            profile.update_trust_score()
        self.message_user(request, "Trust scores have been updated based on verified endorsements.")


@admin.register(MerchantIdentityVerification)
class MerchantIdentityVerificationAdmin(admin.ModelAdmin):
    list_display = ('social_profile', 'submitted_at')
    search_fields = ('social_profile__user__username', 'social_profile__user__email')
    fields = (
        'social_profile',
        'national_id_number',
        'front_document_link',
        'back_document_link',
        'submitted_at',
    )
    readonly_fields = fields

    def has_add_permission(self, _request):
        return False

    def get_urls(self):
        custom_urls = [
            path(
                '<int:object_id>/document/<str:side>/',
                self.admin_site.admin_view(self.download_document),
                name='social_merchantidentityverification_document',
            ),
        ]
        return custom_urls + super().get_urls()

    def _document_link(self, obj, side):
        return format_html(
            '<a href="{}">Download {} ID image</a>',
            reverse(
                'admin:social_merchantidentityverification_document',
                args=(obj.pk, side),
            ),
            side,
        )

    def front_document_link(self, obj):
        return self._document_link(obj, 'front')
    front_document_link.short_description = 'Front of ID'

    def back_document_link(self, obj):
        return self._document_link(obj, 'back')
    back_document_link.short_description = 'Back of ID'

    def download_document(self, request, object_id, side):
        verification = self.get_object(request, str(object_id))
        if verification is None:
            raise Http404
        if not self.has_view_permission(request, verification):
            raise PermissionDenied
        if side == 'front':
            document = verification.id_front_image
        elif side == 'back':
            document = verification.id_back_image
        else:
            raise Http404
        if not document or not document.name:
            raise Http404

        extension = document.name.rsplit('.', 1)[-1].lower()
        response = FileResponse(
            document.open('rb'),
            as_attachment=True,
            filename=f'identity-{side}-{verification.pk}.{extension}',
            content_type='application/octet-stream',
        )
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


@admin.register(BusinessReel)
class BusinessReelAdmin(admin.ModelAdmin):
    """
    Command center for shoppable and professional reels. 
    Monitors speed, engagement metrics, and negotiation floors.
    """
    list_display = (
        'caption_summary', 
        'author', 
        'mode_display',
        'price_display', 
        'likes_count',
        'share_count',
        'download_count',
        'is_low_bandwidth_optimized', 
        'created_at'
    )
    list_filter = ('currency', 'is_low_bandwidth_optimized', 'created_at')
    search_fields = ('author__username', 'caption', 'share_token')
    readonly_fields = ('created_at', 'share_token', 'share_count', 'download_count')
    
    fieldsets = (
        ('Content', {
            'fields': ('author', 'video', 'thumbnail', 'caption')
        }),
        ('Pillar 3: Agentic Pricing', {
            'fields': ('price', 'currency', 'floor_price'),
            'description': "Set the listing price and private floor. Leave empty for Professional Mode."
        }),
        ('Engagement & Sharing', {
            'fields': ('likes', 'share_count', 'download_count', 'share_token'),
            'description': "Social proof and tracking metrics for this reel."
        }),
        ('Pillar 2: Performance', {
            'fields': ('is_low_bandwidth_optimized', 'created_at'),
            'description': "Optimization status for low-latency delivery across Africa."
        }),
    )

    def mode_display(self, obj):
        return "💼 Business" if obj.price else "🎨 Pro"
    mode_display.short_description = 'Reel Mode'

    def caption_summary(self, obj):
        return obj.caption[:50] + "..." if len(obj.caption) > 50 else obj.caption
    caption_summary.short_description = 'Caption'

    def likes_count(self, obj):
        return obj.total_likes
    likes_count.short_description = '❤️'

    def price_display(self, obj):
        if obj.price:
            return f"{obj.currency} {obj.price:,}"
        return "Showcase Only"
    price_display.short_description = 'Public Price'

    def floor_display(self, obj):
        if not obj.price:
            return "N/A"
        floor = obj.get_negotiation_floor()
        # Handle cases where get_negotiation_floor might return an F() expression or None
        try:
            return f"{obj.currency} {float(floor):,.2f}"
        except (TypeError, ValueError):
            return "Calculating..."
    floor_display.short_description = 'AI Floor'


@admin.register(SecureMessage)
class SecureMessageAdmin(admin.ModelAdmin):
    """
    Monitor the 'Hire' protocol conversations and ecosystem engagement.
    """
    list_display = ('sender', 'recipient', 'related_reel', 'timestamp', 'is_read')
    list_filter = ('is_read', 'timestamp', 'is_encrypted')
    search_fields = ('sender__username', 'recipient__username', 'content')
    readonly_fields = ('timestamp',)
    
    fieldsets = (
        ('Participants', {
            'fields': ('sender', 'recipient', 'related_reel')
        }),
        ('Message Content', {
            'fields': ('content', 'is_encrypted', 'is_read')
        }),
        ('Metadata', {
            'fields': ('timestamp',)
        }),
    )


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
            'fields': ('professional', 'client', 'video_clip', 'is_verified_transaction')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )

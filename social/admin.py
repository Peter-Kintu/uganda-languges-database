from django.contrib import admin
from django import forms
from .models import (
    SocialProfile, BusinessReel, VideoEndorsement, SecureMessage,
    YouTubePartnership, YouTubeChannel, YouTubeVideo
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
        'auto_negotiation_enabled'
    )
    list_filter = ('is_verified_merchant', 'auto_negotiation_enabled')
    search_fields = ('user__username', 'user__email')
    actions = ['recalculate_trust']
    
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

    @admin.action(description="Recalculate selected Trust Scores")
    def recalculate_trust(self, request, queryset):
        for profile in queryset:
            profile.update_trust_score()
        self.message_user(request, "Trust scores have been updated based on verified endorsements.")


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


# --- PILLAR 5: YOUTUBE PARTNERSHIP ADMIN ---

class YouTubeChannelInline(admin.TabularInline):
    """Inline management of YouTube channels within partnership."""
    model = YouTubeChannel
    extra = 1
    readonly_fields = ('last_synced_at', 'total_videos_synced', 'added_at')
    fields = ('channel_id', 'channel_name', 'is_syncing', 'sync_frequency_hours', 'total_videos_synced', 'last_synced_at')


@admin.register(YouTubePartnership)
class YouTubePartnershipAdmin(admin.ModelAdmin):
    """
    Manage YouTube content partnerships.
    Track applications, approvals, and sync status.
    """
    list_display = (
        'user', 
        'status_badge', 
        'is_active', 
        'channel_count',
        'applied_at', 
        'approved_at'
    )
    list_filter = ('status', 'is_active', 'applied_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('applied_at', 'approved_at', 'daily_quota_used', 'last_quota_reset')
    inlines = [YouTubeChannelInline]
    actions = ['approve_partnership', 'reject_partnership', 'suspend_partnership']
    
    fieldsets = (
        ('User & Status', {
            'fields': ('user', 'status', 'is_active')
        }),
        ('Application', {
            'fields': ('partnership_description', 'applied_at', 'approved_at')
        }),
        ('API Quota', {
            'fields': ('daily_quota_used', 'last_quota_reset'),
            'classes': ('collapse',),
            'description': "YouTube API v3 quota tracking (10,000 units/day limit)"
        }),
    )
    
    def status_badge(self, obj):
        """Display status with emoji badge."""
        badges = {
            'pending': '🟡 Pending',
            'approved': '🟢 Approved',
            'rejected': '🔴 Rejected',
            'suspended': '⛔ Suspended',
        }
        return badges.get(obj.status, obj.status)
    status_badge.short_description = 'Status'
    
    def channel_count(self, obj):
        """Show number of active channels."""
        count = obj.channels.filter(is_syncing=True).count()
        return f"{count} channels"
    channel_count.short_description = 'Active Channels'
    
    @admin.action(description="Approve selected partnerships")
    def approve_partnership(self, request, queryset):
        """Approve a partnership application."""
        from django.utils import timezone
        updated = queryset.update(status='approved', is_active=True, approved_at=timezone.now())
        self.message_user(request, f"✅ {updated} partnership(s) approved.")
    
    @admin.action(description="Reject selected partnerships")
    def reject_partnership(self, request, queryset):
        """Reject a partnership application."""
        updated = queryset.update(status='rejected', is_active=False)
        self.message_user(request, f"❌ {updated} partnership(s) rejected.")
    
    @admin.action(description="Suspend selected partnerships")
    def suspend_partnership(self, request, queryset):
        """Suspend an approved partnership."""
        updated = queryset.update(status='suspended', is_active=False)
        self.message_user(request, f"⛔ {updated} partnership(s) suspended.")


@admin.register(YouTubeChannel)
class YouTubeChannelAdmin(admin.ModelAdmin):
    """
    Manage individual YouTube channels being synced.
    Monitor sync status and video counts.
    """
    list_display = (
        'channel_name',
        'partnership_user',
        'is_syncing',
        'sync_frequency_hours',
        'total_videos_synced',
        'last_synced_at',
        'video_count'
    )
    list_filter = ('is_syncing', 'sync_frequency_hours', 'last_synced_at')
    search_fields = ('channel_id', 'channel_name', 'partnership__user__username')
    readonly_fields = ('last_synced_at', 'total_videos_synced', 'added_at', 'channel_id')
    actions = ['force_sync_channel', 'disable_channel', 'enable_channel']
    
    fieldsets = (
        ('YouTube Channel', {
            'fields': ('partnership', 'channel_id', 'channel_name', 'channel_url', 'channel_thumbnail')
        }),
        ('Sync Settings', {
            'fields': ('is_syncing', 'sync_frequency_hours', 'last_synced_at', 'total_videos_synced')
        }),
        ('Metadata', {
            'fields': ('added_at',)
        }),
    )
    
    def partnership_user(self, obj):
        """Display the partner user."""
        return obj.partnership.user.username
    partnership_user.short_description = 'Partner'
    
    def video_count(self, obj):
        """Show number of videos from this channel."""
        count = obj.videos.count()
        return f"{count} videos"
    video_count.short_description = 'Videos'
    
    @admin.action(description="Force sync selected channels now")
    def force_sync_channel(self, request, queryset):
        """Manually trigger sync for selected channels."""
        from .youtube_service import YouTubeSyncService
        sync_service = YouTubeSyncService()
        total_synced = 0
        
        for channel in queryset:
            result = sync_service.sync_channel_videos(channel)
            total_synced += result['synced']
        
        self.message_user(request, f"✅ Synced {total_synced} videos across {queryset.count()} channels.")
    
    @admin.action(description="Disable syncing for selected channels")
    def disable_channel(self, request, queryset):
        """Disable syncing."""
        updated = queryset.update(is_syncing=False)
        self.message_user(request, f"🛑 {updated} channel(s) disabled.")
    
    @admin.action(description="Enable syncing for selected channels")
    def enable_channel(self, request, queryset):
        """Enable syncing."""
        updated = queryset.update(is_syncing=True)
        self.message_user(request, f"▶️ {updated} channel(s) enabled.")


@admin.register(YouTubeVideo)
class YouTubeVideoAdmin(admin.ModelAdmin):
    """
    Monitor YouTube videos that have been synced.
    Track their engagement and linked BusinessReels.
    """
    list_display = (
        'title_summary',
        'channel',
        'youtube_views',
        'youtube_likes',
        'business_reel_status',
        'published_at',
        'synced_at'
    )
    list_filter = ('is_active', 'published_at', 'synced_at')
    search_fields = ('title', 'youtube_id', 'channel__channel_name')
    readonly_fields = ('youtube_id', 'youtube_views', 'youtube_likes', 'synced_at')
    
    fieldsets = (
        ('YouTube Metadata', {
            'fields': ('youtube_id', 'channel', 'title', 'description', 'youtube_url')
        }),
        ('Media', {
            'fields': ('thumbnail_url', 'duration_seconds')
        }),
        ('Engagement', {
            'fields': ('youtube_views', 'youtube_likes', 'published_at')
        }),
        ('Sync Status', {
            'fields': ('business_reel', 'is_active', 'synced_at')
        }),
    )
    
    def title_summary(self, obj):
        """Show truncated title."""
        return obj.title[:50] + "..." if len(obj.title) > 50 else obj.title
    title_summary.short_description = 'Title'
    
    def business_reel_status(self, obj):
        """Show if video has a linked BusinessReel."""
        if obj.business_reel:
            return f"✅ Linked (ID: {obj.business_reel.id})"
        return "⚠️ Not linked"
    business_reel_status.short_description = 'BusinessReel'

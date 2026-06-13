from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Count
from django.core.files.storage import storages # Import storage routing
from cloudinary.models import CloudinaryField
import cloudinary
import uuid
import hashlib
import hmac
from decimal import Decimal

# Link to your existing CustomUser
User = settings.AUTH_USER_MODEL

# --- PILLAR 1 & 4: IDENTITY ---

class SocialProfile(models.Model):
    """
    Extends the user with capabilities for verified social commerce.
    Contains the Trust Ledger (Pillar 1) and Bento Config (Pillar 4).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='social_profile')
    
    # --- PILLAR 1: TRUST LEDGER ---
    trust_score = models.FloatField(
        default=0.0, 
        help_text="Dynamic score (0-100) based on verified transactions."
    )
    # NEW: Cryptographic signature to prevent database tampering (The Digital Seal)
    trust_signature = models.CharField(max_length=255, blank=True)
    
    verified_deals_count = models.PositiveIntegerField(default=0)
    is_verified_merchant = models.BooleanField(
        default=False, 
        help_text="Awarded after AI assessment and identity verification."
    )

    # --- CONTACT SETTINGS ---
    whatsapp_number = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        help_text="Enter with country code (e.g., 256700000000). Used for 'Hire Me' / 'Order' buttons."
    )
    
    # --- PILLAR 3: GLOBAL AGENTIC SETTINGS ---
    auto_negotiation_enabled = models.BooleanField(
        default=True,
        help_text="Enables the AI Agent to haggle on behalf of the user."
    )
    minimum_margin_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=10.00
    )
    
    # --- PILLAR 4: BENTO LAYOUT ---
    bento_config = models.JSONField(default=dict, blank=True)

    def generate_trust_signature(self):
        """Creates a cryptographic hash of the score using the server's secret key."""
        data = f"{self.user.id}-{self.trust_score}"
        return hmac.new(
            settings.SECRET_KEY.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()

    def update_trust_score(self):
        """
        Logic to recalculate trust based on verified endorsements and engagement.
        UPDATED: Each like on any of the user's reels adds 5% to the score.
        """
        total_likes = BusinessReel.objects.filter(author=self.user).aggregate(
            total=models.Count('likes')
        )['total'] or 0

        endorsements = self.user.received_endorsements.filter(is_verified_transaction=True).count()
        
        new_score = (total_likes * 5) + (self.verified_deals_count * 2) + (endorsements * 5)
        
        self.trust_score = min(100.0, float(new_score))
        self.trust_signature = self.generate_trust_signature()
        self.save()

    @property
    def is_trust_verified(self):
        """Protocol check: Verifies if the database score matches the cryptographic seal."""
        if not self.trust_signature:
            return False
        return hmac.compare_digest(self.trust_signature, self.generate_trust_signature())

    def __str__(self):
        return f"Social Layer: {self.user.username} ({self.trust_score}%)"


# --- PILLAR 2 & 3: COMMERCE ---

class BusinessReel(models.Model):
    """
    Shoppable Reel / Professional Portfolio: 
    High-speed video gateway with optional Agentic Pricing.
    UPDATED: Three-tier hybrid storage (IndexedDB → Local Server → Cloudinary CDN).
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    
    # --- THREE-TIER STORAGE SYSTEM ---
    STORAGE_TIERS = [
        ('LOCAL', 'Django Server Hard Drive'),
        ('CLOUDINARY', 'Cloudinary Global CDN')
    ]
    storage_tier = models.CharField(
        max_length=15,
        choices=STORAGE_TIERS,
        default='LOCAL',
        help_text="Where this video is currently stored."
    )
    
    # Tier 1: Local disk (Choice B - Initial staging)
    local_video = models.FileField(
        upload_to='reels/staging/',
        blank=True,
        null=True,
        help_text="Video stored on server disk (low-cost, handles initial uploads)."
    )
    
    # Tier 3: Cloudinary CDN (Choice C - High-traffic promotion)
    cloudinary_public_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Cloudinary public ID for promoted viral content."
    )
    
    # Legacy field - kept for backward compatibility
    video = CloudinaryField(
        'video',
        folder='africana_reels/',
        blank=True,
        null=True,
        help_text="Optimized for low-bandwidth delivery across Africa."
    )
    
    external_video_url = models.URLField(
        blank=True,
        null=True,
        help_text="External video source URL for synced YouTube reels."
    )
    
    # Thumbnails remain on Cloudinary for AI-driven transformation/caching
    thumbnail = CloudinaryField('image', folder='africana_thumbnails/', blank=True, null=True)
    external_thumbnail_url = models.URLField(
        blank=True,
        null=True,
        help_text="External thumbnail URL for synced YouTube reels."
    )
    caption = models.TextField(max_length=500)
    
    # Language and tags for content categorization
    language = models.CharField(max_length=10, default='en', help_text="Content language code (e.g., 'en', 'sw', 'lg')")
    tags = models.TextField(blank=True, help_text="Comma-separated tags for content discovery")
    
    # --- AGENTIC PRICING ---
    price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Public price. Leave blank for professional/work-sample content."
    )
    currency = models.CharField(max_length=10, default="UGX", blank=True)
    floor_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Absolute minimum the AI Agent can accept. (Secret)"
    )

    # --- ENGAGEMENT TRACKING & VIRALITY METRICS ---
    likes = models.ManyToManyField(User, related_name='liked_reels', blank=True)
    share_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(
        default=0,
        help_text="Track views to trigger tier promotion to Cloudinary."
    )
    
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    is_low_bandwidth_optimized = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def total_likes(self):
        return self.likes.count()

    def get_negotiation_floor(self):
        """Calculates floor price from specific field or global margin."""
        if not self.price:
            return None
        if self.floor_price:
            return self.floor_price
        
        try:
            margin = self.author.social_profile.minimum_margin_percent
            return self.price * (Decimal('1.0') - (Decimal(str(margin)) / Decimal('100.0')))
        except (SocialProfile.DoesNotExist, AttributeError):
            margin = Decimal('10.00')
            return self.price * (Decimal('1.00') - (margin / Decimal('100.00')))

    @property
    def source_video_url(self):
        """
        Tier-based video URL routing: Dynamically returns the correct resource link.
        If video was promoted to Cloudinary, use that. Otherwise, use local server disk.
        Feed.html uses this property transparently without changes.
        """
        if self.external_video_url:
            # YouTube shorts or external sources always use the external link
            return self.external_video_url
        
        if self.storage_tier == 'CLOUDINARY' and self.cloudinary_public_id:
            # High-traffic video promoted to Cloudinary CDN
            cloud_name = cloudinary.config().cloud_name
            return f"https://res.cloudinary.com/{cloud_name}/video/upload/{self.cloudinary_public_id}.mp4"
        
        if self.local_video:
            # New or low-traffic video stored on local server disk
            return self.local_video.url
        
        # Fallback to legacy Cloudinary field if it exists
        if self.video and hasattr(self.video, 'url'):
            return self.video.url
        
        return ''

    @property
    def source_thumbnail_url(self):
        """Return the active thumbnail URL for this reel."""
        if self.external_thumbnail_url:
            return self.external_thumbnail_url
        if self.thumbnail and hasattr(self.thumbnail, 'url'):
            return self.thumbnail.url
        return ''

    @property
    def is_external_video(self):
        """Return whether this reel is sourced from an external video URL."""
        return bool(self.external_video_url)

    @property
    def video_embed_url(self):
        """Return an iframe-friendly embed URL for supported external sources."""
        if not self.external_video_url:
            return ''

        video_id = self.extract_youtube_id(self.external_video_url)
        if video_id:
            return (
                f"https://www.youtube-nocookie.com/embed/{video_id}"
                "?autoplay=1&mute=1&controls=0&rel=0&playsinline=1"
            )

        return self.external_video_url

    def extract_youtube_id(self, url):
        """Extract a YouTube video ID from watch, short, embed, or shorts URLs."""
        import re

        patterns = [
            r'(?:youtube\.com/(?:watch\?v=|embed/|shorts/|v/)|youtu\.be/)([A-Za-z0-9_-]{11})',
            r'[?&]v=([A-Za-z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    @property
    def youtube_id(self):
        """Return the 11-char YouTube ID when this reel references an external YouTube URL."""
        if not self.external_video_url:
            return None
        return self.extract_youtube_id(self.external_video_url)

    def __str__(self):
        if self.price:
            return f"Business Reel by {self.author.username} - {self.currency} {self.price}"
        return f"Professional Reel by {self.author.username}"


# --- SOVEREIGN MESSAGING ---

class SecureMessage(models.Model):
    """
    Internal 'Hire' protocol. 
    """
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    related_reel = models.ForeignKey(BusinessReel, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    is_encrypted = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Secure Msg: {self.sender.username} -> {self.recipient.username}"


class VideoEndorsement(models.Model):
    """
    Verified Proof of Work: 15-second client testimonials.
    Uses Cloudinary for short-form video transformations.
    """
    professional = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_endorsements')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_endorsements')
    video_clip = CloudinaryField(
        'video', 
        resource_type='video', 
        folder='endorsements/'
    )
    is_verified_transaction = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Endorsement for {self.professional.username}"


# --- PILLAR 5: YOUTUBE PARTNERSHIP & CONTENT SYNDICATION ---

class YouTubePartnership(models.Model):
    """
    Manages user partnerships for pulling YouTube content.
    Allows authorized users to sync videos from specific channels.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('suspended', 'Suspended'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='youtube_partnership')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_active = models.BooleanField(default=False)
    
    # API quota tracking
    daily_quota_used = models.PositiveIntegerField(default=0)
    last_quota_reset = models.DateTimeField(auto_now_add=True)
    
    # Branding
    partnership_description = models.TextField(
        blank=True,
        help_text="Why do you want to partner with us?"
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-applied_at']
    
    def __str__(self):
        return f"YouTube Partnership: {self.user.username} ({self.status})"


class YouTubeChannel(models.Model):
    """
    Stores YouTube channels that a partner wants to sync from.
    Each partner can manage multiple channels.
    """
    partnership = models.ForeignKey(YouTubePartnership, on_delete=models.CASCADE, related_name='channels')
    
    # YouTube identifiers
    channel_id = models.CharField(max_length=100, unique=True, help_text="YouTube Channel ID (e.g., UCxxxxxx)")
    channel_name = models.CharField(max_length=255)
    channel_url = models.URLField(blank=True)
    channel_thumbnail = models.URLField(blank=True, help_text="Channel avatar URL from YouTube")
    
    # Sync settings
    is_syncing = models.BooleanField(default=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    sync_frequency_hours = models.PositiveIntegerField(
        default=24,
        help_text="How often to check for new videos (in hours)"
    )
    last_sync_error = models.TextField(
        blank=True,
        null=True,
        help_text="Stores the last YouTube sync error message for this channel."
    )
    sync_error_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="YouTube API error code or reason from the last sync attempt."
    )
    requires_reauth = models.BooleanField(
        default=False,
        help_text="Set when this channel needs authorization or access revalidation."
    )
    
    # Metadata
    total_videos_synced = models.PositiveIntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-added_at']
        unique_together = ('partnership', 'channel_id')
    
    def __str__(self):
        return f"{self.channel_name} ({self.partnership.user.username})"


class YouTubeVideo(models.Model):
    """
    Stores YouTube videos pulled via API.
    Linked to BusinessReel for seamless integration.
    Maintains the video as a bridge between YouTube and the social feed.
    """
    # YouTube identifiers
    youtube_id = models.CharField(max_length=100, unique=True, help_text="YouTube Video ID")
    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE, related_name='videos')
    
    # Video metadata
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField()
    youtube_url = models.URLField()
    duration_seconds = models.PositiveIntegerField(default=0)
    
    # YouTube stats
    youtube_views = models.PositiveIntegerField(default=0)
    youtube_likes = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField()
    
    # Link to BusinessReel (automatic conversion)
    business_reel = models.ForeignKey(
        BusinessReel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='source_youtube'
    )
    
    # Sync tracking
    is_active = models.BooleanField(default=True)
    synced_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-published_at']
    
    def __str__(self):
        return f"{self.title} (Channel: {self.channel.channel_name})"


# --- AUTOMATION SIGNALS ---

@receiver(post_save, sender=User)
def handle_user_social_profile(sender, instance, created, **kwargs):
    """Ensures every user has a SocialProfile and handles sync."""
    if created:
        profile, _ = SocialProfile.objects.get_or_create(user=instance)
        profile.trust_signature = profile.generate_trust_signature()
        profile.save()
    else:
        if hasattr(instance, 'social_profile'):
            instance.social_profile.save()

@receiver(post_save, sender=VideoEndorsement)
def auto_update_trust_on_endorsement(sender, instance, created, **kwargs):
    """Pillar 1 Automation: Recalculates Trust Score when endorsements are verified."""
    if instance.is_verified_transaction:
        try:
            instance.professional.social_profile.update_trust_score()
        except SocialProfile.DoesNotExist:
            pass
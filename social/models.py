from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Count
from django.core.files.storage import storages # Import storage routing
from cloudinary.models import CloudinaryField
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
    UPDATED: Now using Cloudflare R2 for heavy video storage.
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    
    # VIDEO STORAGE UPDATE: Routed to Cloudflare R2 via 'reels_video' backend
    video = models.FileField(
        upload_to='africana_reels/',
        storage=storages['reels_video'],
        help_text="Stored on Cloudflare R2 for zero-egress high-speed delivery."
    )
    
    # Thumbnails remain on Cloudinary for AI-driven transformation/caching
    thumbnail = CloudinaryField('image', folder='africana_thumbnails/', blank=True, null=True)
    caption = models.TextField(max_length=500)
    
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

    # --- ENGAGEMENT TRACKING ---
    likes = models.ManyToManyField(User, related_name='liked_reels', blank=True)
    share_count = models.PositiveIntegerField(default=0)
    download_count = models.PositiveIntegerField(default=0)
    
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
from django.db import models
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField
import uuid

# Link to your existing CustomUser
User = settings.AUTH_USER_MODEL

# --- PILLAR 1 & 4: IDENTITY ---

class SocialProfile(models.Model):
    """
    Extends the user with capabilities for verified social commerce.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='social_profile')
    
    # --- PILLAR 1: TRUST LEDGER ---
    trust_score = models.FloatField(
        default=0.0, 
        help_text="Dynamic score (0-100) based on verified transactions."
    )
    verified_deals_count = models.PositiveIntegerField(default=0)
    is_verified_merchant = models.BooleanField(
        default=False, 
        help_text="Awarded after AI assessment and identity verification."
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

    def update_trust_score(self):
        """Logic to recalculate trust based on verified endorsements."""
        endorsements = self.user.received_endorsements.filter(is_verified_transaction=True).count()
        self.trust_score = min(100.0, (self.verified_deals_count * 2) + (endorsements * 5))
        self.save()

    def __str__(self):
        return f"Social Layer: {self.user.username} ({self.trust_score}%)"


# --- PILLAR 2 & 3: COMMERCE ---

class BusinessReel(models.Model):
    """
    TikTok 2.0 Shoppable Reel: High-speed video gateway with Agentic Pricing.
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    
    # FIX: Removed 'options' dict to prevent TypeError: Field.__init__() got unexpected keyword argument.
    # Optimization is now handled by resource_type and folder flags.
    video = CloudinaryField(
        'video', 
        resource_type='video',
        folder='africana_reels/',
        overwrite=True,
        help_text="Optimized for low-bandwidth delivery."
    )
    thumbnail = CloudinaryField('image', folder='africana_thumbnails/', blank=True, null=True)
    caption = models.TextField(max_length=500)
    
    # --- AGENTIC PRICING ---
    price = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default="UGX")
    floor_price = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Absolute minimum the AI Agent can accept."
    )
    
    is_low_bandwidth_optimized = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def get_negotiation_floor(self):
        if self.floor_price:
            return self.floor_price
        margin = self.author.social_profile.minimum_margin_percent
        return self.price * (1 - (margin / 100))

    def __str__(self):
        return f"Reel by {self.author.username} - {self.currency} {self.price}"


# --- SOVEREIGN MESSAGING (Native Encrypted "Hire" Logic) ---

class SecureMessage(models.Model):
    """
    Internal E2EE-style messaging for the 'Hire' protocol.
    """
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    
    # Reference to the reel that triggered the 'Hire' intent
    related_reel = models.ForeignKey(BusinessReel, on_delete=models.SET_NULL, null=True, blank=True)
    
    content = models.TextField(help_text="Stored message content.")
    is_encrypted = models.BooleanField(default=True)
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"Secure Msg from {self.sender.username} to {self.recipient.username}"


class VideoEndorsement(models.Model):
    professional = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_endorsements')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_endorsements')
    
    # FIX: Cleaned up CloudinaryField here as well
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
    if created:
        SocialProfile.objects.get_or_create(user=instance)
    else:
        if hasattr(instance, 'social_profile'):
            instance.social_profile.save()

@receiver(post_save, sender=VideoEndorsement)
def auto_update_trust_on_endorsement(sender, instance, created, **kwargs):
    if instance.is_verified_transaction:
        instance.professional.social_profile.update_trust_score()
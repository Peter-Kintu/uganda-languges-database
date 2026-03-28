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
        # Example logic: 2 pts per deal + 5 pts per verified testimonial
        self.trust_score = min(100.0, (self.verified_deals_count * 2) + (endorsements * 5))
        self.save()

    def __str__(self):
        return f"Social Layer: {self.user.username} ({self.trust_score}%)"


# --- PILLAR 2 & 3: COMMERCE ---

class BusinessReel(models.Model):
    """
    TikTok 2.0 Shoppable Reel: High-speed video gateway.
    """
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    video = CloudinaryField(
        'video', 
        resource_type='video', 
        help_text="Optimized for low-bandwidth delivery."
    )
    thumbnail = CloudinaryField('image', blank=True, null=True)
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
    
    # --- OPTIMIZATION ---
    is_low_bandwidth_optimized = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def get_negotiation_floor(self):
        """Calculates floor price from specific field or global margin."""
        if self.floor_price:
            return self.floor_price
        margin = self.author.social_profile.minimum_margin_percent
        return self.price * (1 - (margin / 100))

    def __str__(self):
        return f"Reel by {self.author.username} - {self.currency} {self.price}"


class VideoEndorsement(models.Model):
    """
    Verified Proof of Work: 15-second client testimonials.
    """
    professional = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_endorsements')
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_endorsements')
    video_clip = CloudinaryField('video', resource_type='video')
    is_verified_transaction = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Endorsement for {self.professional.username}"


# --- AUTOMATION SIGNALS ---

@receiver(post_save, sender=User)
def create_user_social_profile(sender, instance, created, **kwargs):
    """
    Automatically creates a SocialProfile whenever a new User is registered.
    """
    if created:
        SocialProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=User)
def save_user_social_profile(sender, instance, **kwargs):
    """
    Ensures the profile is saved whenever the User object is updated.
    """
    if hasattr(instance, 'social_profile'):
        instance.social_profile.save()
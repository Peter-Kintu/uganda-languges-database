from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField

# --- Custom User Model ---

class CustomUser(AbstractUser):
    """
    Extends the default Django User model and includes related_name fixes
    to resolve clashes with the default auth.User.
    """
    headline = models.CharField(_("Headline"), max_length=255, blank=True, null=True, 
                                help_text=_("A professional title or summary, like 'Senior Django Developer'"))
    about = models.TextField(_("About Summary"), blank=True, null=True, 
                             help_text=_("A summary of your professional journey and goals."))
    location = models.CharField(_("Location"), max_length=100, blank=True, null=True)

    profile_image = CloudinaryField('profile_image', blank=True, null=True, 
                                    help_text=_("Upload a professional profile picture."))

    # --- REFERRAL LOGIC PROPERTY ---
    @property
    def total_referral_earnings(self):
        """Sums all commissions from confirmed orders attributed to this user."""
        # Local import to avoid circular dependency
        from eshop.models import Order
        from django.db.models import Sum
        
        total = Order.objects.filter(
            referrer=self, 
            status='Completed'
        ).aggregate(Sum('total_commission'))['total_commission__sum']
        
        return total or 0

    # --- FIX FOR RELATED NAME CLASHES ---
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        related_name="customuser_set",
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        related_name="customuser_permissions_set",
        related_query_name="customuser_permission",
    )
    
    def get_full_name(self):
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()

    def __str__(self):
        return self.username


# --- Profile Component Models ---

class Experience(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='experiences')
    title = models.CharField(max_length=100)
    company_name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name_plural = "Experiences"

    def __str__(self):
        return f"{self.title} at {self.company_name}"
        
    @property
    def company_initial(self):
        return self.company_name[0].upper() if self.company_name else '?'


class Education(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='education')
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=100)
    field_of_study = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-end_date']
        verbose_name_plural = "Education"

    def __str__(self):
        return f"{self.degree} from {self.institution}"


class Skill(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=50, unique=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Skills"

    def __str__(self):
        return self.name


class SocialConnection(models.Model):
    PLATFORM_CHOICES = (
        ('linkedin', 'LinkedIn (Professional)'),
        ('github', 'GitHub (Developer)'),
        ('portfolio', 'Personal Portfolio'),
        ('x', 'X / Twitter'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('medium', 'Medium / Blog'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='social_connections')
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    url = models.URLField(max_length=500)
    access_token = models.CharField(max_length=512, blank=True, null=True) 

    class Meta:
        unique_together = ('user', 'platform')
        verbose_name = "Social Connection"
        verbose_name_plural = "Social Connections"

    def __str__(self):
        return f"{self.user.username}'s {self.get_platform_display()} link"


# --- Notification Model (The Alert System) ---

class Notification(models.Model):
    # Changed related_name to 'profile_notifications' to resolve clash with eshop.Notification
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile_notifications'
    )
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Alert for {self.user.username}: {self.title}"


# --- Signals ---

@receiver(post_save, sender='eshop.Order')
def notify_referrer_on_completion(sender, instance, **kwargs):
    """
    Only notify if the order was just marked 'Completed' and there is a referrer.
    Uses string reference 'eshop.Order' to avoid circular imports.
    """
    if instance.status == 'Completed' and instance.referrer:
        Notification.objects.create(
            user=instance.referrer,
            title="Commission Earned! 💰",
            message=(
                f"Success! Someone bought items via your link. "
                f"You earned {instance.total_commission}!"
            )
        )
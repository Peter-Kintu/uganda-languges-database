from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.utils.translation import gettext_lazy as _
from cloudinary.models import CloudinaryField

# --- Custom User Model ---

class CustomUser(AbstractUser):
    """
    Extends the default Django User model and includes related_name fixes
    to resolve clashes with the default auth.User.
    """
    # Profile Info for the LinkedIn-style layout
    headline = models.CharField(_("Headline"), max_length=255, blank=True, null=True, 
                                help_text=_("A professional title or summary, like 'Senior Django Developer'"))
    about = models.TextField(_("About Summary"), blank=True, null=True, 
                             help_text=_("A summary of your professional journey and goals."))
    location = models.CharField(_("Location"), max_length=100, blank=True, null=True)

    # Profile Media
    profile_image = CloudinaryField('profile_image', blank=True, null=True, 
                                    help_text=_("Upload a professional profile picture."))

    # --- FIX FOR RELATED NAME CLASHES (E304 ERROR) ---
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to. A user will get all permissions '
                    'granted to each of their groups.'),
        related_name="customuser_set", # Custom related name
        related_query_name="customuser",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="customuser_permissions_set", # Custom related name
        related_query_name="customuser_permission",
    )
    
    def get_full_name(self):
        """Returns the first_name plus the last_name, with a space in between."""
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def __str__(self):
        return self.username
    
# --- Profile Component Models ---

class Experience(models.Model):
    """Stores a user's professional experience."""
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
    """Stores a user's educational background."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='education')
    institution = models.CharField(max_length=200)
    degree = models.CharField(max_length=100)
    # NOTE: Assuming 'field_of_study' exists as per the views.py mock logic in the previous turn
    field_of_study = models.CharField(max_length=100, blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-end_date']
        verbose_name_plural = "Education"

    def __str__(self):
        return f"{self.degree} from {self.institution}"

class Skill(models.Model):
    """Stores a user's professional skills."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=50, unique=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Skills"

    def __str__(self):
        return self.name

# --- NEW MODEL: SocialConnection ---
class SocialConnection(models.Model):
    """
    Stores a user's connections to external professional/social platforms,
    preparing for OAuth and data fetching.
    """
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
    url = models.URLField(max_length=500, help_text="The full URL to your profile.")
    # This token field is crucial for future OAuth integration
    access_token = models.CharField(max_length=512, blank=True, null=True,
                                    help_text="OAuth token for API access (managed by system).") 

    class Meta:
        unique_together = ('user', 'platform')
        verbose_name = "Social Connection"
        verbose_name_plural = "Social Connections"
    
    def __str__(self):
        return f"{self.user.username}'s {self.get_platform_display()} link"
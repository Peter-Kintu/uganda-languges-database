from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission # Imported Group and Permission
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
    # We must explicitly define the groups and user_permissions fields 
    # and give them unique related_name values.
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name="custom_user_set", # <-- UNIQUE RELATED_NAME
        related_query_name="custom_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="custom_user_permissions_set", # <-- UNIQUE RELATED_NAME
        related_query_name="custom_user_permission",
    )
    # --------------------------------------------------

    def __str__(self):
        return self.username

# --- Related Profile Models (No changes needed here) ---

class Experience(models.Model):
    """Stores a user's professional work experience."""
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
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        ordering = ['-end_date']
        verbose_name_plural = "Education"

    def __str__(self):
        return f"{self.degree} from {self.institution}"

class Skill(models.Model):
    """Stores a specific skill associated with a user."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['name']
        
    def __str__(self):
        return self.name
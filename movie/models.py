import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings

class Movie(models.Model):
    # Basic Movie Information
    name = models.CharField(max_length=255, verbose_name="Movie Title")
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(verbose_name="Plot Summary")
    
    # AI Content & Recommendation Fields
    ai_summary = models.TextField(blank=True, null=True, help_text="AI-generated catchy summary")
    ai_recommendation_tags = models.CharField(max_length=500, blank=True, help_text="AI keywords")
    
    # Metadata & Categorization
    genre = models.CharField(max_length=100)
    category = models.CharField(
        max_length=100, 
        choices=[('trending', 'Trending'), ('new', 'New Release'), ('date_night', 'Date Night')],
        default='new'
    )
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0.0)
    release_date = models.DateField(null=True, blank=True)
    
    # Affiliate & Media Links (Your Revenue Source)
    image_url = models.TextField(help_text="Direct URL for movie posters")
    trailer_url = models.URLField(blank=True, null=True)
    affiliate_url = models.TextField(help_text="Link to watch on Amazon/Netflix/Disney+")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Metrics for AI Recommendation Engine
    view_count = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Order(models.Model):
    """Tracks affiliate clicks for your earnings."""
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, null=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, default='Redirected')
    created_at = models.DateTimeField(auto_now_add=True)
from django.db import models
from django.utils.text import slugify

class Product(models.Model):
    # Core Product Information
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_negotiable = models.BooleanField(default=False)
    vendor_name = models.CharField(max_length=100, default='Anonymous Seller')
    
    # Seller Contact & Media
    whatsapp_number = models.CharField(max_length=20)
    tiktok_url = models.URLField(max_length=200, null=True, blank=True)
    
    # Product Images
    image = models.ImageField(upload_to='products/')
    
    # Cultural & Localization Tags
    language_tag = models.CharField(max_length=50) # e.g., 'Luganda', 'Acholi'
    
    # A slug for pretty URLs
    slug = models.SlugField(max_length=200, unique=True, editable=False)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
        
    def __str__(self):
        return self.name
# models.py

from django.db import models
from django.utils.text import slugify
from cloudinary.models import CloudinaryField  # NEW import

# New imports for the cart feature
from django.conf import settings

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
    # Change this field to use CloudinaryField
    image = CloudinaryField('image') # UPDATED FIELD
    
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

# NEW MODELS FOR THE SHOPPING CART
class Cart(models.Model):
    session_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart for session: {self.session_key}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def total_price(self):
        return self.product.price * self.quantity
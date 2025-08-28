from django.db import models
from django.utils.text import slugify

# New imports for the cart feature
from django.conf import settings

class Product(models.Model):
    

    slug = models.SlugField(max_length=100, unique=True, blank=True)

    # Core Product Information
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_negotiable = models.BooleanField(default=False)
    vendor_name = models.CharField(max_length=100, default='Anonymous Seller')
    
    # Seller Contact & Media
    whatsapp_number = models.CharField(max_length=20)
    tiktok_url = models.URLField(max_length=200, null=True, blank=True)
    
    # Product Images (you'll need to install Pillow for image processing)
    image = models.ImageField(upload_to='products/', default='products/placeholder.jpg')
    
    # Cultural & Localization Tags
    language_tag = models.CharField(max_length=50) # e.g., 'Luganda', 'Acholi'
    
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

# NEW MODELS FOR THE SHOPPING CART
class Cart(models.Model):
    session_key = models.CharField(max_length=40, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    STATUS_CHOICES = [
        ('open', 'Open'),
        ('confirmed', 'Confirmed'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    @property
    def cart_total(self):
        return sum(item.total_price for item in self.items.all())
    
    def get_items_by_vendor(self, vendor_name):
       return self.items.filter(product__vendor_name=vendor_name)

    def __str__(self):
        return f"Cart for session: {self.session_key}"
    
   
    

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        if self.product and self.product.price:
            return self.product.price * self.quantity
        return 0

    def update_quantity(self, new_quantity):
       if new_quantity > 0:
        self.quantity = new_quantity
        self.save()    

    @property
    def vendor(self):
        return self.product.vendor_name

    def __str__(self):
        product_name = self.product.name if self.product else "Unknown Product"
        return f"{self.quantity} x {product_name}"
 
    class Meta:
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        ordering = ['-added_at']



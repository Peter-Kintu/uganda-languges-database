import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from cloudinary.models import CloudinaryField
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- Product Model ---

class Product(models.Model):
    # Media Fields
    image = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', resource_type='video', blank=True, null=True)
    
    # AI Negotiation Fields
    negotiated_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_negotiable = models.BooleanField(default=False)
    
    # Core Product Information
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Referral System Field
    referral_commission = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="The amount paid to the referrer upon a successful sale."
    )
    
    # Currency Settings
    CURRENCY_CHOICES = [
        ('UGX', 'UGX (Ugandan Shilling)'),
        ('USD', 'USD (US Dollar)'),
        ('KES', 'KES (Kenyan Shilling)'),
        ('NGN', 'NGN (Nigerian Naira)'),
        ('GHS', 'GHS (Ghanaian Cedi)'),
        ('ZAR', 'ZAR (South African Rand)'),
        ('TZS', 'TZS (Tanzanian Shilling)'),
        ('RWF', 'RWF (Rwandan Franc)'),
        ('EGP', 'EGP (Egyptian Pound)'),
    ]
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='UGX')
    country = models.CharField(max_length=50)

    # Vendor Information
    vendor_name = models.CharField(max_length=100, default='Anonymous Seller')
    whatsapp_number = models.CharField(max_length=20)
    tiktok_url = models.URLField(max_length=200, null=True, blank=True)

    def get_currency_code(self):
        if self.currency and self.currency != 'UGX':
            return self.currency
            
        currency_map = {
            'Uganda': 'UGX', 'Kenya': 'KES', 'Tanzania': 'TZS',
            'Rwanda': 'RWF', 'Nigeria': 'NGN', 'Ghana': 'GHS',
            'South Africa': 'ZAR', 'Egypt': 'EGP', 'Zimbabwe': 'USD', 'USA': 'USD',
        }
        return currency_map.get(self.country, self.currency)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            self.slug = base_slug
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                unique_suffix = uuid.uuid4().hex[:6]
                self.slug = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_currency_code()})"

    class Meta:
        ordering = ['name']


# --- Cart and CartItem Models ---

class Cart(models.Model):
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    STATUS_CHOICES = [('open', 'Open'), ('confirmed', 'Confirmed'), ('expired', 'Expired')]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    @property
    def cart_total(self):
        return sum(item.total_price for item in self.items.all())

    def __str__(self):
        return f"Cart {self.session_key}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        base_price = self.product.negotiated_price or self.product.price
        return (base_price * self.quantity) if base_price else 0

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"


# --- Order Models (The Referral Bridge) ---

class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    # Links purchase to the buyer
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='purchases'
    )
    
    # Automatically tracks who gets the commission
    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='attributed_orders'
    )
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        """Auto-assign referrer from buyer profile if not manually set."""
        if not self.referrer and hasattr(self.buyer, 'referred_by'):
            self.referrer = self.buyer.referred_by
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order #{self.id} - {self.buyer.username}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='order_items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
    commission_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)


    def __str__(self):
        return f"{self.product.name} (Qty: {self.quantity})"
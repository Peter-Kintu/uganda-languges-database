import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from cloudinary.models import CloudinaryField
from django.db.models.signals import post_save
from django.dispatch import receiver

# --- Product Model ---

class Product(models.Model):
    # Marketplace Source Fields
    SOURCE_CHOICES = [
        ('local', 'Local Marketplace'),
        ('aliexpress', 'AliExpress'),
        ('jumia', 'Jumia'),
    ]
    source = models.CharField(
        max_length=20, 
        choices=SOURCE_CHOICES, 
        default='local',
        db_index=True,
        help_text="Where this product originates from."
    )
    external_id = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        db_index=True,
        help_text="ID from external marketplace (e.g., AliExpress productId, Jumia SKU)"
    )
    
    # TextField used to handle long URLs without overwhelming Neon/Postgres
    affiliate_url = models.TextField(
        blank=True, 
        null=True,
        help_text="Affiliate link to redirect buyers to external marketplace"
    )
    image_url = models.TextField(
        blank=True, 
        null=True, 
        help_text="Direct URL for images from external marketplaces"
    )

    # Tracking Metadata
    last_synced = models.DateTimeField(auto_now=True, help_text="Last time this product was updated via API")

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
    impressions = models.PositiveIntegerField(default=0, db_index=True)
    
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

    CATEGORY_CHOICES = [
        ('vehicles', 'Vehicles'),
        ('property', 'Property'),
        ('phones-tablets', 'Phones & Tablets'),
        ('electronics', 'Electronics'),
        ('home-furniture', 'Home, Furniture & Appliances'),
        ('fashion', 'Fashion'),
        ('beauty-personal-care', 'Beauty & Personal Care'),
        ('services', 'Services'),
        ('repair-construction', 'Repair & Construction'),
        ('commercial-tools', 'Commercial Equipment & Tools'),
        ('leisure-activities', 'Leisure & Activities'),
        ('babies-kids', 'Babies & Kids'),
        ('food-agriculture', 'Food, Agriculture & Farming'),
        ('hotel-budget', 'Simple Hotel Meals (3,000-10,000)'),
        ('hotel-1star', '1-Star Hotel Dining'),
        ('hotel-2star', '2-Star Hotel Dining'),
        ('hotel-3star', '3-Star Hotel Dining'),
        ('hotel-4star', '4-Star Hotel Dining'),
        ('hotel-5star', '5-Star Hotel Dining'),
        ('food-chips', 'Chips & Snacks'),
        ('food-burger', 'Burger & Fast Food'),
        ('food-pizza', 'Pizza & Oven Bakes'),
        ('food-rolex', 'Rolex & Street Rolls'),
        ('food-chicken', 'Chicken & Poultry'),
        ('food-fried-fish', 'Fried Fish & Seafood'),
        ('food-street-food', 'Street Food & Takeaway'),
        ('animals-pets', 'Animals & Pets'),
    ]
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, blank=True, default='', db_index=True)

    # Vendor Information
    vendor_name = models.CharField(max_length=100, default='Anonymous Seller')
    whatsapp_number = models.CharField(max_length=20, blank=True, null=True)
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
        constraints = [
            models.UniqueConstraint(
                fields=['source', 'external_id'], 
                name='unique_product_per_source',
                condition=models.Q(external_id__isnull=False)
            )
        ]


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

    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='purchases'
    )
    
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
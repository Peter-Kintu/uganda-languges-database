import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from cloudinary.models import CloudinaryField

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
    # This allows anyone who shares the link to earn a set amount from the vendor
    referral_commission = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0.00,
        help_text="The amount the vendor pays to the person who shared the link upon a successful sale."
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
        """
        Returns the manually selected currency. 
        If it's the default, it tries to map based on country as a fallback.
        """
        if self.currency and self.currency != 'UGX':
            return self.currency
            
        currency_map = {
            'Uganda': 'UGX',
            'Kenya': 'KES',
            'Tanzania': 'TZS',
            'Rwanda': 'RWF',
            'Nigeria': 'NGN',
            'Ghana': 'GHS',
            'South Africa': 'ZAR',
            'Egypt': 'EGP',
            'Zimbabwe': 'USD',
            'USA': 'USD',
        }
        return currency_map.get(self.country, self.currency)

    def save(self, *args, **kwargs):
        """
        Custom save method to handle unique slug generation.
        """
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
    
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('confirmed', 'Confirmed'),
        ('expired', 'Expired'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')

    @property
    def cart_total(self):
        """Calculates total based on individual item prices."""
        return sum(item.total_price for item in self.items.all())

    def get_cart_currency(self):
        """Returns the currency code of the first item in the cart."""
        first_item = self.items.first()
        if first_item:
            return first_item.product.get_currency_code()
        return "UGX"
    
    def get_items_by_vendor(self, vendor_name):
       return self.items.filter(product__vendor_name=vendor_name)

    def __str__(self):
        return f"Cart {self.session_key} - Total Items: {self.items.count()}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_price(self):
        """
        Calculates price. 
        Uses negotiated_price (AI) if available, otherwise standard price.
        """
        base_price = self.product.negotiated_price if self.product.negotiated_price else self.product.price
            
        if base_price:
            return base_price * self.quantity
        return 0

    def update_quantity(self, new_quantity):
       if new_quantity > 0:
            self.quantity = new_quantity
            self.save()    

    @property
    def vendor(self):
        return self.product.vendor_name

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Cart"
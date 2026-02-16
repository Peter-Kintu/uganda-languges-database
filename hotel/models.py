import uuid
from django.db import models
from django.utils.text import slugify
from django.conf import settings
from cloudinary.models import CloudinaryField

class Accommodation(models.Model):
    SOURCE_CHOICES = [
        ('local', 'Local Lodge/Hotel'),
        ('travelpayouts', 'Travelpayouts (Trip.com/Agoda)'),
    ]
    
    AFRICAN_COUNTRIES = [
        ('Algeria', 'Algeria'), ('Angola', 'Angola'), ('Benin', 'Benin'), ('Botswana', 'Botswana'),
        ('Burkina Faso', 'Burkina Faso'), ('Burundi', 'Burundi'), ('Cabo Verde', 'Cabo Verde'),
        ('Cameroon', 'Cameroon'), ('Central African Republic', 'Central African Republic'),
        ('Chad', 'Chad'), ('Comoros', 'Comoros'), ('Congo', 'Congo'), ('Djibouti', 'Djibouti'),
        ('Egypt', 'Egypt'), ('Equatorial Guinea', 'Equatorial Guinea'), ('Eritrea', 'Eritrea'),
        ('Eswatini', 'Eswatini'), ('Ethiopia', 'Ethiopia'), ('Gabon', 'Gabon'), ('Gambia', 'Gambia'),
        ('Ghana', 'Ghana'), ('Guinea', 'Guinea'), ('Ivory Coast', 'Ivory Coast'), ('Kenya', 'Kenya'),
        ('Lesotho', 'Lesotho'), ('Liberia', 'Liberia'), ('Libya', 'Libya'), ('Madagascar', 'Madagascar'),
        ('Malawi', 'Malawi'), ('Mali', 'Mali'), ('Mauritania', 'Mauritania'), ('Mauritius', 'Mauritius'),
        ('Morocco', 'Morocco'), ('Mozambique', 'Mozambique'), ('Namibia', 'Namibia'), ('Niger', 'Niger'),
        ('Nigeria', 'Nigeria'), ('Rwanda', 'Rwanda'), ('Senegal', 'Senegal'), ('Seychelles', 'Seychelles'),
        ('Sierra Leone', 'Sierra Leone'), ('Somalia', 'Somalia'), ('South Africa', 'South Africa'),
        ('South Sudan', 'South Sudan'), ('Sudan', 'Sudan'), ('Tanzania', 'Tanzania'), ('Togo', 'Togo'),
        ('Tunisia', 'Tunisia'), ('Uganda', 'Uganda'), ('Zambia', 'Zambia'), ('Zimbabwe', 'Zimbabwe'),
    ]

    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='local')
    external_id = models.CharField(max_length=200, blank=True, null=True) 
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField()
    
    country = models.CharField(max_length=100, choices=AFRICAN_COUNTRIES)
    city = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    stars = models.IntegerField(default=0)
    
    price_per_night = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    
    whatsapp_number = models.CharField(max_length=20, blank=True)
    tiktok_url = models.URLField(max_length=500, blank=True, null=True, help_text="Link to the TikTok property tour video")
    affiliate_url = models.TextField(blank=True, null=True) 
    
    image = CloudinaryField('image', blank=True, null=True)
    image_url = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.name}-{self.city}")
            self.slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.city}, {self.country}"
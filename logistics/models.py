import uuid

from django.conf import settings
from django.db import models


class CourierProvider(models.Model):
    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=40, unique=True)
    api_base_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class DeliveryQuote(models.Model):
    STATUS_CHOICES = [('quoted', 'Quoted'), ('expired', 'Expired')]
    order = models.ForeignKey('eshop.Order', on_delete=models.CASCADE, related_name='delivery_quotes')
    provider = models.ForeignKey(CourierProvider, on_delete=models.PROTECT, related_name='quotes')
    quote_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='UGX')
    eta_minutes = models.PositiveIntegerField(default=120)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='quoted')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)


class Shipment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('assigned', 'Assigned'), ('picked_up', 'Picked up'),
        ('in_transit', 'In transit'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled'),
    ]
    order = models.OneToOneField('eshop.Order', on_delete=models.CASCADE, related_name='shipment')
    provider = models.ForeignKey(CourierProvider, on_delete=models.PROTECT, related_name='shipments')
    external_id = models.CharField(max_length=120, unique=True)
    tracking_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    driver_name = models.CharField(max_length=120, blank=True)
    driver_phone = models.CharField(max_length=30, blank=True)
    dispatched_at = models.DateTimeField(blank=True, null=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class TrackingEvent(models.Model):
    shipment = models.ForeignKey(Shipment, on_delete=models.CASCADE, related_name='tracking_events')
    status = models.CharField(max_length=20)
    note = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    external_event_id = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

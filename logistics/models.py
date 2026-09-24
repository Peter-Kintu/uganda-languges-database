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


class DriverProfile(models.Model):
    STATUS_CHOICES = [('pending', 'Pending verification'), ('verified', 'Verified'), ('suspended', 'Suspended')]
    VEHICLE_CHOICES = [('standard', 'Standard car'), ('comfort', 'Comfort car'), ('boda', 'Boda')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='driver_profile')
    phone = models.CharField(max_length=30)
    whatsapp_phone = models.CharField(max_length=30, blank=True)
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES, default='standard')
    vehicle_make = models.CharField(max_length=80, blank=True)
    vehicle_plate = models.CharField(max_length=30)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    is_available = models.BooleanField(default=False)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    last_location_at = models.DateTimeField(blank=True, null=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5)
    completed_trips = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.vehicle_plate})'


class RideRequest(models.Model):
    RIDE_TYPES = [('standard', 'Standard ride'), ('comfort', 'Comfort ride'), ('boda', 'Boda ride')]
    PAYMENT_METHODS = [('momo', 'Mobile Money'), ('airtel', 'Airtel Money'), ('cash', 'Cash'), ('card', 'Card')]
    STATUS_CHOICES = [
        ('requested', 'Requested'), ('matching', 'Matching'), ('assigned', 'Driver assigned'),
        ('arrived', 'Driver arrived'), ('in_progress', 'In progress'), ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_requests')
    driver = models.ForeignKey(DriverProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='rides')
    pickup_landmark = models.CharField(max_length=255)
    dropoff_landmark = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    pickup_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    dropoff_latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    dropoff_longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    ride_type = models.CharField(max_length=20, choices=RIDE_TYPES, default='standard')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='momo')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    estimated_fare_min = models.PositiveIntegerField()
    estimated_fare_max = models.PositiveIntegerField()
    distance_km = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    eta_minutes = models.PositiveIntegerField(default=10)
    cancellation_reason = models.CharField(max_length=255, blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f'Ride #{self.pk} - {self.status}'


class RideLocation(models.Model):
    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE, related_name='locations')
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='location_pings')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy_meters = models.PositiveIntegerField(blank=True, null=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-recorded_at']


class RidePayment(models.Model):
    PROVIDERS = [('momo', 'MTN MoMo'), ('airtel', 'Airtel Money'), ('card', 'Card'), ('cash', 'Cash')]
    STATUS_CHOICES = [('pending', 'Pending'), ('paid', 'Paid'), ('failed', 'Failed'), ('refunded', 'Refunded')]

    ride = models.OneToOneField(RideRequest, on_delete=models.CASCADE, related_name='payment')
    provider = models.CharField(max_length=20, choices=PROVIDERS)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider_transaction_id = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class RideRating(models.Model):
    ride = models.OneToOneField(RideRequest, on_delete=models.CASCADE, related_name='rating_record')
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_ride_ratings')
    driver = models.ForeignKey(DriverProfile, on_delete=models.CASCADE, related_name='received_ride_ratings')
    score = models.PositiveSmallIntegerField()
    comment = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class SafetyReport(models.Model):
    CATEGORY_CHOICES = [('emergency', 'Emergency'), ('unsafe_driving', 'Unsafe driving'), ('lost_item', 'Lost item'), ('other', 'Other')]
    STATUS_CHOICES = [('open', 'Open'), ('reviewing', 'Reviewing'), ('resolved', 'Resolved')]

    ride = models.ForeignKey(RideRequest, on_delete=models.CASCADE, related_name='safety_reports')
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='safety_reports')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    details = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)


class SupportTicket(models.Model):
    PRIORITY_CHOICES = [('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent')]
    STATUS_CHOICES = [('open', 'Open'), ('in_progress', 'In progress'), ('resolved', 'Resolved')]

    requester = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_support_tickets')
    ride = models.ForeignKey(RideRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name='support_tickets')
    subject = models.CharField(max_length=180)
    details = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

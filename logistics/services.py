from dataclasses import dataclass
from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
import os
from uuid import uuid4

from django.db import transaction
from django.utils import timezone


@dataclass
class QuoteResult:
    amount: Decimal
    currency: str
    eta_minutes: int


@dataclass
class DispatchResult:
    external_id: str
    tracking_url: str


class CourierAdapter:
    code = 'mock'

    def quote(self, *, order):
        return QuoteResult(amount=Decimal('5000.00'), currency=order.currency, eta_minutes=90)

    def dispatch(self, *, order, quote):
        shipment_id = f'{self.code}-{uuid4().hex[:12]}'
        return DispatchResult(external_id=shipment_id, tracking_url='')


class CourierRegistry:
    _adapters = {'mock': CourierAdapter()}

    @classmethod
    def get(cls, code):
        return cls._adapters.get(code, cls._adapters['mock'])


@dataclass
class RideFare:
    distance_km: Decimal
    minimum: int
    maximum: int
    eta_minutes: int
    confidence: str


def _haversine_km(latitude_one, longitude_one, latitude_two, longitude_two):
    latitude_one, longitude_one, latitude_two, longitude_two = map(
        radians, [float(latitude_one), float(longitude_one), float(latitude_two), float(longitude_two)]
    )
    delta_latitude = latitude_two - latitude_one
    delta_longitude = longitude_two - longitude_one
    value = sin(delta_latitude / 2) ** 2 + cos(latitude_one) * cos(latitude_two) * sin(delta_longitude / 2) ** 2
    return 6371 * 2 * asin(sqrt(value))


def calculate_ride_fare(*, ride_type, pickup_latitude=None, pickup_longitude=None, dropoff_latitude=None, dropoff_longitude=None):
    has_coordinates = all(value is not None for value in (pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude))
    distance = _haversine_km(pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude) if has_coordinates else 5.0
    traffic_factor = max(Decimal('0.8'), Decimal(os.getenv('RIDE_TRAFFIC_FACTOR', '1.0')))
    fuel_factor = max(Decimal('0.8'), Decimal(os.getenv('RIDE_FUEL_FACTOR', '1.0')))
    rates = {
        'standard': (Decimal('3000'), Decimal('1800')),
        'comfort': (Decimal('5000'), Decimal('2600')),
        'boda': (Decimal('1800'), Decimal('1200')),
    }
    base, per_km = rates.get(ride_type, rates['standard'])
    raw_fare = (base + per_km * Decimal(str(max(distance, 0.5)))) * traffic_factor * fuel_factor
    return RideFare(
        distance_km=Decimal(str(round(distance, 2))),
        minimum=max(2000, int(raw_fare * Decimal('0.9'))),
        maximum=max(2500, int(raw_fare * Decimal('1.1'))),
        eta_minutes=max(5, int(distance * 3 + 5)),
        confidence='high' if has_coordinates else 'landmark estimate',
    )


def match_nearest_driver(ride):
    from .models import DriverProfile

    if ride.pickup_latitude is None or ride.pickup_longitude is None:
        return None
    candidates = DriverProfile.objects.filter(
        status='verified', is_available=True, latitude__isnull=False, longitude__isnull=False,
        vehicle_type=ride.ride_type,
    )
    ranked_drivers = []
    for driver in candidates:
        distance = _haversine_km(ride.pickup_latitude, ride.pickup_longitude, driver.latitude, driver.longitude)
        ranked_drivers.append((distance, driver.pk))
    for _, driver_id in sorted(ranked_drivers):
        with transaction.atomic():
            locked_driver = DriverProfile.objects.select_for_update().get(pk=driver_id)
            if not locked_driver.is_available or locked_driver.status != 'verified':
                continue
            locked_driver.is_available = False
            locked_driver.save(update_fields=['is_available', 'updated_at'])
            return locked_driver
    return None


def whatsapp_notification_link(phone, message):
    normalized_phone = ''.join(character for character in phone or '' if character.isdigit() or character == '+')
    return f'https://wa.me/{normalized_phone.lstrip("+")}?text={message.replace(" ", "%20")}' if normalized_phone else ''

from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher
from math import asin, cos, radians, sin, sqrt
import os
import re
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


LOCAL_LANDMARKS = {
    'acacia mall': (0.3476, 32.5917),
    'clock tower': (0.3075, 32.5700),
    'chez lando': (0.3538, 32.6135),
    'kampala road': (0.3152, 32.5813),
    'nakawa market': (0.3417, 32.6350),
    'cbd': (0.3152, 32.5813),
    'old taxi park': (0.3115, 32.5721),
    'new taxi park': (0.3148, 32.5689),
    'mulago hospital': (0.3470, 32.5790),
    'makerere university': (0.3350, 32.5680),
    'uganda museum': (0.3456, 32.5910),
    'garden city': (0.3227, 32.5847),
    'kisementi': (0.3472, 32.5925),
    'kisasi': (0.3790, 32.6080),
    'entebbe airport': (0.0424, 32.4435),
}


def _normalize_landmark(value):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9 ]', ' ', (value or '').lower())).strip()


def resolve_landmark_coordinates(raw_text, *, minimum_score=0.72):
    """Return approximate local coordinates for a familiar landmark description."""
    normalized = _normalize_landmark(raw_text)
    if not normalized:
        return None
    for landmark, coordinates in LOCAL_LANDMARKS.items():
        if landmark in normalized:
            return coordinates
    best_match = max(
        LOCAL_LANDMARKS,
        key=lambda landmark: SequenceMatcher(None, landmark, normalized).ratio(),
    )
    score = SequenceMatcher(None, best_match, normalized).ratio()
    return LOCAL_LANDMARKS[best_match] if score >= minimum_score else None


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
    with transaction.atomic():
        candidates = DriverProfile.objects.select_for_update().filter(
            status='verified', is_available=True, latitude__isnull=False, longitude__isnull=False,
            vehicle_type=ride.ride_type,
        )
        ranked_drivers = [
            (_haversine_km(ride.pickup_latitude, ride.pickup_longitude, driver.latitude, driver.longitude), driver)
            for driver in candidates
        ]
        if ranked_drivers:
            _, selected_driver = min(ranked_drivers, key=lambda candidate: (candidate[0], candidate[1].pk))
            selected_driver.is_available = False
            selected_driver.save(update_fields=['is_available', 'updated_at'])
            return selected_driver
    return None


def whatsapp_notification_link(phone, message):
    normalized_phone = ''.join(character for character in phone or '' if character.isdigit() or character == '+')
    return f'https://wa.me/{normalized_phone.lstrip("+")}?text={message.replace(" ", "%20")}' if normalized_phone else ''

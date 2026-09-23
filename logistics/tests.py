import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eshop.models import Order
from .models import CourierProvider, DriverProfile, RideLocation, RidePayment, RideRating, RideRequest, SafetyReport, Shipment, SupportTicket, TrackingEvent


class CourierTrackingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='test-pass')
        self.order = Order.objects.create(buyer=self.user, total_amount=Decimal('10000'), currency='UGX', status='dispatching')
        self.provider = CourierProvider.objects.create(name='Mock Courier', code='mock')
        self.shipment = Shipment.objects.create(order=self.order, provider=self.provider, external_id='mock-123', status='assigned')

    def test_provider_webhook_updates_order_and_is_idempotent(self):
        payload = {'external_id': 'mock-123', 'status': 'delivered', 'event_id': 'evt-1'}
        response = self.client.post(reverse('logistics:provider_webhook', args=['mock']), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')
        self.assertEqual(TrackingEvent.objects.filter(external_event_id='evt-1').count(), 1)
        self.client.post(reverse('logistics:provider_webhook', args=['mock']), data=json.dumps(payload), content_type='application/json')
        self.assertEqual(TrackingEvent.objects.filter(external_event_id='evt-1').count(), 1)


class RideWorkflowTests(TestCase):
    def setUp(self):
        self.rider = get_user_model().objects.create_user(username='rider', password='test-pass')
        self.driver_user = get_user_model().objects.create_user(username='driver', first_name='Amina', password='test-pass')
        self.driver = DriverProfile.objects.create(
            user=self.driver_user, phone='+256700000001', vehicle_type='standard', vehicle_plate='UXX 123A',
            status='verified', is_available=True, latitude='0.3150', longitude='32.5810',
        )
        self.client.force_login(self.rider)

    def test_request_matches_available_driver_and_creates_payment(self):
        response = self.client.post(reverse('logistics:request_ride'), data=json.dumps({
            'pickup': 'Acacia Mall main gate', 'dropoff': 'Clock Tower taxi stage', 'ride_type': 'standard',
            'payment': 'Mobile Money', 'pickup_latitude': 0.3150, 'pickup_longitude': 32.5810,
            'dropoff_latitude': 0.3075, 'dropoff_longitude': 32.5700,
        }), content_type='application/json')

        self.assertEqual(response.status_code, 201)
        ride = RideRequest.objects.get()
        self.assertEqual(ride.status, 'assigned')
        self.assertEqual(ride.driver_id, self.driver.id)
        self.assertEqual(RidePayment.objects.get(ride=ride).provider, 'momo')
        self.driver.refresh_from_db()
        self.assertFalse(self.driver.is_available)

    def test_completed_ride_accepts_rating_and_safety_report(self):
        ride = RideRequest.objects.create(
            rider=self.rider, driver=self.driver, pickup_landmark='A', dropoff_landmark='B', ride_type='standard',
            payment_method='cash', status='completed', estimated_fare_min=5000, estimated_fare_max=7000,
        )
        rating_response = self.client.post(reverse('logistics:rate_ride', args=[ride.id]), data=json.dumps({'score': 5, 'comment': 'Good trip'}), content_type='application/json')
        safety_response = self.client.post(reverse('logistics:safety_report', args=[ride.id]), data=json.dumps({'category': 'lost_item', 'details': 'Umbrella left in vehicle'}), content_type='application/json')

        self.assertEqual(rating_response.status_code, 200)
        self.assertEqual(safety_response.status_code, 200)
        self.assertEqual(RideRating.objects.get(ride=ride).score, 5)
        self.assertEqual(SafetyReport.objects.get(ride=ride).category, 'lost_item')

    def test_tracking_returns_latest_driver_location(self):
        ride = RideRequest.objects.create(
            rider=self.rider, driver=self.driver, pickup_landmark='A', dropoff_landmark='B', ride_type='standard',
            payment_method='cash', status='in_progress', estimated_fare_min=5000, estimated_fare_max=7000,
        )
        RideLocation.objects.create(ride=ride, driver=self.driver, latitude='0.3160', longitude='32.5820')

        response = self.client.get(reverse('logistics:ride_tracking', args=[ride.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['path'][0]['latitude'], '0.3160000')

    def test_emergency_report_creates_urgent_support_ticket(self):
        ride = RideRequest.objects.create(
            rider=self.rider, driver=self.driver, pickup_landmark='A', dropoff_landmark='B', ride_type='standard',
            payment_method='cash', status='in_progress', estimated_fare_min=5000, estimated_fare_max=7000,
        )

        response = self.client.post(reverse('logistics:safety_report', args=[ride.id]), data=json.dumps({'category': 'emergency', 'details': 'Need immediate help'}), content_type='application/json')

        self.assertEqual(response.status_code, 200)
        ticket = SupportTicket.objects.get(ride=ride)
        self.assertEqual(ticket.priority, 'urgent')
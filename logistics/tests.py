import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eshop.models import Order
from .models import CourierProvider, Shipment, TrackingEvent


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
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import AffiliateEvent, AffiliatePayout, CommercePayment, Order, Product


class EscrowOrderTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='buyer', password='test-pass')
        self.creator = get_user_model().objects.create_user(username='creator', password='test-pass')
        self.product = Product.objects.create(name='Basket', description='Handmade basket', price=Decimal('10000'), country='Uganda', vendor_user=self.creator)
        self.order = Order.objects.create(buyer=self.user, total_amount=Decimal('10000'), currency='UGX', status='delivered')
        CommercePayment.objects.create(order=self.order, pesapal_order_id='eshop-test-1', amount=self.order.total_amount, currency='UGX', status='paid')
        AffiliateEvent.objects.create(creator=self.creator, product=self.product, order=self.order, event_type='conversion', commission_amount=Decimal('500'))
        AffiliatePayout.objects.create(creator=self.creator, order=self.order, amount=Decimal('500'))

    def test_buyer_confirmation_releases_escrow_and_commission(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('eshop:confirm_delivery', args=[self.order.id]))
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'released')
        self.assertEqual(self.order.escrow_status, 'released')
        self.assertEqual(AffiliatePayout.objects.get(order=self.order).status, 'payable')

    def test_unpaid_order_cannot_be_confirmed(self):
        self.order.status = 'payment_pending'
        self.order.save(update_fields=['status'])
        self.client.force_login(self.user)
        response = self.client.post(reverse('eshop:confirm_delivery', args=[self.order.id]))
        self.assertEqual(response.status_code, 409)

    @patch('users.views._pesapal_request')
    def test_pesapal_get_ipn_funds_escrow(self, pesapal_request):
        pesapal_request.side_effect = [
            {'token': 'test-token'},
            {'status': 'COMPLETED', 'confirmation_code': 'MOMO-123'},
        ]
        self.order.status = 'payment_pending'
        self.order.escrow_status = 'pending'
        self.order.save(update_fields=['status', 'escrow_status'])
        payment = self.order.commerce_payment
        payment.tracking_id = 'tracking-1'
        payment.save(update_fields=['tracking_id'])

        response = self.client.get(reverse('pesapal_ipn'), {'OrderTrackingId': 'tracking-1'})

        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(self.order.escrow_status, 'funded')
        self.assertEqual(self.order.status, 'escrowed')

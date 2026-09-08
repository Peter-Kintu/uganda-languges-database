from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

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
        self.assertEqual(AffiliatePayout.objects.get(order=self.order).status, 'payable')

    def test_unpaid_order_cannot_be_confirmed(self):
        self.order.status = 'payment_pending'
        self.order.save(update_fields=['status'])
        self.client.force_login(self.user)
        response = self.client.post(reverse('eshop:confirm_delivery', args=[self.order.id]))
        self.assertEqual(response.status_code, 409)

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .models import AffiliateEvent, AffiliatePayout, Cart, CartItem, CommercePayment, Order, Product
from .views import get_aliexpress_search_groups


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

    def test_legacy_pesapal_ipn_is_disabled(self):
        response = self.client.get(reverse('pesapal_ipn'), {'OrderTrackingId': 'tracking-1'})

        self.assertEqual(response.status_code, 410)


class AliExpressSearchConfigTests(TestCase):
    def test_phone_case_and_screen_queries_are_included(self):
        groups = get_aliexpress_search_groups()
        queries = [group['query'].lower() for group in groups]

        self.assertTrue(any('smartphone' in query or 'android phone' in query for query in queries))
        self.assertTrue(any('phone case' in query or 'case' in query and 'phone' in query for query in queries))
        self.assertTrue(any('screen protector' in query or 'lcd touch screen' in query or 'digitizer' in query for query in queries))


class NegotiationFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='negotiator', password='test-pass')
        self.creator = get_user_model().objects.create_user(username='seller', password='test-pass')
        self.product = Product.objects.create(
            name='Negotiable basket',
            description='Handmade basket',
            price=Decimal('10000'),
            country='Uganda',
            vendor_user=self.creator,
            is_negotiable=True,
        )
        self.client.force_login(self.user)

    def test_accepted_offer_shows_negotiated_price_and_close_action(self):
        response = self.client.post(
            reverse('eshop:ai_negotiation', args=[self.product.slug]),
            {'user_message': 'I can offer UGX 9000'},
        )

        self.assertRedirects(response, reverse('eshop:ai_negotiation', args=[self.product.slug]))
        page = self.client.get(reverse('eshop:ai_negotiation', args=[self.product.slug]))
        self.assertContains(page, 'Accept UGX 9,000')
        self.assertNotContains(page, 'Accept UGX 10,000')

    def test_accepted_price_flows_into_cart_and_delivery_total(self):
        self.client.post(
            reverse('eshop:ai_negotiation', args=[self.product.slug]),
            {'user_message': 'I can offer UGX 9000'},
        )
        self.client.get(reverse('eshop:accept_negotiated_price', args=[self.product.slug]))
        self.client.post(reverse('eshop:add_to_cart', args=[self.product.id]))

        cart_page = self.client.get(reverse('eshop:view_cart'))
        delivery_page = self.client.get(reverse('eshop:delivery_location'))

        self.assertContains(cart_page, '9,000')
        self.assertContains(delivery_page, '9000')

    def test_seller_storefront_uses_real_profile_data(self):
        self.creator.headline = 'Fashion Seller'
        self.creator.location = 'Kampala, Uganda'
        self.creator.profile_image = 'https://example.com/seller-avatar.jpg'
        self.creator.save(update_fields=['headline', 'location', 'profile_image'])

        self.product.vendor_name = 'Grace Boutique'
        self.product.save(update_fields=['vendor_name'])

        response = self.client.get(reverse('eshop:seller_storefront', args=[self.creator.username]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grace Boutique')
        self.assertContains(response, 'Fashion Seller')
        self.assertContains(response, 'Kampala, Uganda')
        self.assertContains(response, self.product.name)

    def test_repeated_low_offer_holds_price_and_suggests_bulk_option(self):
        self.client.post(
            reverse('eshop:ai_negotiation', args=[self.product.slug]),
            {'user_message': 'I can offer UGX 2000'},
        )
        self.client.post(
            reverse('eshop:ai_negotiation', args=[self.product.slug]),
            {'user_message': 'I can offer UGX 2000'},
        )

        page = self.client.get(reverse('eshop:ai_negotiation', args=[self.product.slug]))
        self.assertContains(page, 'bulk order')
        self.assertContains(page, 'Feed, transport, and handling costs')

    def test_extreme_low_offer_gets_firm_local_response(self):
        product = Product.objects.create(
            name='Cassava',
            description='Fresh cassava from the farm',
            price=Decimal('3000'),
            country='Uganda',
            vendor_user=self.creator,
            is_negotiable=True,
        )
        self.client.post(
            reverse('eshop:ai_negotiation', args=[product.slug]),
            {'user_message': 'I can offer UGX 290'},
        )

        page = self.client.get(reverse('eshop:ai_negotiation', args=[product.slug]))
        self.assertContains(page, 'Haba!')
        self.assertContains(page, 'too little')
        self.assertContains(page, 'fresh from the farm')
        self.assertNotContains(page, 'makes sense if you are trying to stay within budget')

    def test_extra_zero_is_checked_before_treating_offer_as_real(self):
        product = Product.objects.create(
            name='Cassava',
            description='Fresh cassava from the farm',
            price=Decimal('3000'),
            country='Uganda',
            vendor_user=self.creator,
            is_negotiable=True,
        )
        self.client.post(
            reverse('eshop:ai_negotiation', args=[product.slug]),
            {'user_message': '20000'},
        )

        page = self.client.get(reverse('eshop:ai_negotiation', args=[product.slug]))
        self.assertContains(page, 'did you mean')
        self.assertContains(page, 'extra zero')

    def test_counteroffer_does_not_drop_after_a_firm_counter(self):
        product = Product.objects.create(
            name='Cassava',
            description='Fresh cassava from the farm',
            price=Decimal('3000'),
            country='Uganda',
            vendor_user=self.creator,
            is_negotiable=True,
        )
        url = reverse('eshop:ai_negotiation', args=[product.slug])
        self.client.post(url, {'user_message': '2000'})
        self.client.post(url, {'user_message': '2300'})

        page = self.client.get(url)
        self.assertContains(page, 'UGX 2,900')
        self.assertNotContains(page, 'UGX 2,800')

    def test_raising_offers_move_the_counter_and_rotate_response_copy(self):
        product = Product.objects.create(
            name='Broilers',
            description='Heavy farm-raised broilers',
            price=Decimal('30000'),
            country='Uganda',
            vendor_user=self.creator,
            is_negotiable=True,
        )
        url = reverse('eshop:ai_negotiation', args=[product.slug])
        self.client.post(url, {'user_message': '23000'})
        self.client.post(url, {'user_message': '24000'})
        self.client.post(url, {'user_message': '25000'})

        page = self.client.get(url)
        body = page.content.decode()
        self.assertIn('UGX 27,300', body)
        self.assertIn('Okay, you', body)
        self.assertIn('squeezing me! But let me see', body)
        self.assertIn('farm pickup and transport', body)
        self.assertNotIn("This is close to the seller's limit now.", body)

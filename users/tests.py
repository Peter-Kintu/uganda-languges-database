from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users.models import PesapalPayment, UserSubscription


User = get_user_model()


class PesapalIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pesapal_user',
            email='pesapal@example.com',
            password='secret1234',
        )

    @patch('users.views.requests.post')
    def test_start_checkout_returns_redirect(self, mock_post):
        mock_post.side_effect = [
            SimpleNamespace(status_code=200, ok=True, json=lambda: {'token': 'token-123'}),
            SimpleNamespace(status_code=200, ok=True, json=lambda: {
                'order_tracking_id': 'tracking-123',
                'redirect_url': 'https://pesapal.example/pay/123',
            }),
        ]

        self.client.force_login(self.user)
        response = self.client.post(reverse('users:pesapal_start_checkout'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://pesapal.example/pay/123')
        self.assertTrue(PesapalPayment.objects.filter(user=self.user).exists())
        self.assertTrue(UserSubscription.objects.filter(user=self.user).exists())

    @patch('users.views.requests.post')
    def test_ipn_marks_subscription_active(self, mock_post):
        payment = PesapalPayment.objects.create(
            user=self.user,
            order_id='order-1',
            tracking_id='tracking-456',
            amount='30000.00',
            currency='UGX',
            description='30-Day Pro Business Pass',
            status='PENDING',
        )
        subscription = UserSubscription.objects.create(user=self.user, status='pending')
        payment.subscription = subscription
        payment.save(update_fields=['subscription'])

        mock_post.side_effect = [
            SimpleNamespace(status_code=200, ok=True, json=lambda: {'token': 'token-456'}),
            SimpleNamespace(status_code=200, ok=True, json=lambda: {
                'status': 'COMPLETED',
                'amount': '30000.00',
                'currency': 'UGX',
            }),
        ]

        response = self.client.post(
            reverse('users:pesapal_ipn'),
            {'OrderTrackingId': 'tracking-456', 'OrderNotificationType': 'CHANGE'},
        )

        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        subscription.refresh_from_db()
        self.assertEqual(payment.status, 'PAID')
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.status, 'active')

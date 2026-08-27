from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from myuganda.middleware import WordPressProbeBlockMiddleware
from users.models import PesapalPayment, UserSubscription
from users.views import _get_pesapal_config, _pesapal_request


User = get_user_model()


class ExploitProbeDefenseTests(TestCase):
    def test_rest_route_probe_is_denied_with_404(self):
        request = RequestFactory().get('/', {'rest_route': '/wp/v2/users'})
        middleware = WordPressProbeBlockMiddleware(lambda request: None)
        response = middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)

    def test_wordpress_manifest_probe_is_denied_with_404(self):
        request = RequestFactory().get('/wp-includes/wlwmanifest.xml')
        middleware = WordPressProbeBlockMiddleware(lambda request: None)
        response = middleware.process_request(request)
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 404)


class PesapalConfigTests(TestCase):
    def test_default_pesapal_base_url_uses_production_domain(self):
        config = _get_pesapal_config()
        self.assertEqual(config['base_url'], 'https://pay.pesapal.com/v3')

    def test_pesapal_request_path_is_joined_without_double_api_segment(self):
        config = _get_pesapal_config()
        base_url = config['base_url'].rstrip('/')
        if base_url.endswith('/api'):
            base_url = base_url[:-4]
        url = f"{base_url}/api/Auth/RequestToken"
        self.assertEqual(url, 'https://pay.pesapal.com/v3/api/Auth/RequestToken')

    @patch.dict('os.environ', {
        'PESAPAL_CONSUMER_KEY': 'live-key',
        'PESAPAL_CONSUMER_SECRET': 'live-secret',
    })
    @patch('users.views.requests.post')
    def test_auth_request_uses_json_credentials_and_required_headers(self, mock_post):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            ok=True,
            json=lambda: {'token': 'token-123'},
        )

        _pesapal_request('post', 'Auth/RequestToken')

        mock_post.assert_called_once_with(
            'https://pay.pesapal.com/v3/api/Auth/RequestToken',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            json={
                'consumer_key': 'live-key',
                'consumer_secret': 'live-secret',
            },
            timeout=20,
        )


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

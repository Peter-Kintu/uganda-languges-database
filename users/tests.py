from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import RequestFactory, TestCase
from django.urls import reverse

from myuganda.middleware import WordPressProbeBlockMiddleware
from users.models import AgentMemory, AgentPlan, EventBooking, PesapalPayment, UserSubscription
from users.tasks import send_user_notification_task
from users.views import _get_pesapal_config, _pesapal_request, _send_welcome_email


User = get_user_model()


class AgentCommandTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='agent_user', password='secret1234')
        self.client.force_login(self.user)

    def test_memory_is_user_scoped_and_persistent(self):
        response = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'remember', 'key': 'target_role', 'value': 'Python developer'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AgentMemory.objects.get(user=self.user, key='target_role').value, 'Python developer')

    def test_plan_checkpoint_advances_and_completes(self):
        response = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'plan', 'title': 'Launch portfolio', 'goal': 'Get interviews', 'steps': ['Write CV', 'Apply']},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        plan_id = response.json()['plan_id']
        checkpoint = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'checkpoint', 'plan_id': plan_id, 'step': 0, 'evidence': 'CV drafted'},
            content_type='application/json',
        )
        self.assertEqual(checkpoint.status_code, 200)
        self.assertEqual(checkpoint.json()['current_step'], 1)
        self.assertEqual(AgentPlan.objects.get(id=plan_id).steps[0]['status'], 'completed')

    @patch.dict('os.environ', {'BRAVE_SEARCH_API_KEY': ''})
    @patch('users.views.requests.get')
    def test_free_research_fallback_returns_empty_results(self, mock_get):
        mock_get.return_value = SimpleNamespace(text='<html></html>', raise_for_status=lambda: None)
        response = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'research', 'query': 'Uganda software jobs'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sources'], [])

    @patch.dict('os.environ', {'BRAVE_SEARCH_API_KEY': ''})
    @patch('users.views.requests.get')
    def test_free_research_fallback_parses_duckduckgo_lite_results(self, mock_get):
        standard = SimpleNamespace(
            text='<html></html>',
            raise_for_status=lambda: None,
        )
        lite = SimpleNamespace(
            text='<tr><td class="result-link"><a class="result-link" href="https://example.com/jobs">Example Jobs</a></td><td class="result-snippet">Open roles</td></tr>',
            raise_for_status=lambda: None,
        )
        contact_page = SimpleNamespace(
            text='<html><title>Example Jobs</title></html>',
            raise_for_status=lambda: None,
        )
        mock_get.side_effect = [standard, lite, contact_page]

        response = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'research', 'query': 'Example jobs'},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['sources'][0]['url'], 'https://example.com/jobs')

    @patch('users.views._brave_research', return_value=[{
        'title': 'Example Supplier',
        'url': 'https://example.com/contact',
        'excerpt': 'Wholesale supplier',
    }])
    @patch('users.views.requests.get')
    def test_research_returns_public_contacts(self, mock_get, mock_search):
        mock_get.return_value = SimpleNamespace(
            text='<a href="/contact">Contact us</a> sales@example.com +256 700 123 456',
            raise_for_status=lambda: None,
        )
        response = self.client.post(
            reverse('users:agent_command'),
            data={'action': 'research', 'query': 'supplier contact'},
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        contacts = response.json()['contact_results'][0]['contacts']
        self.assertIn('sales@example.com', contacts['emails'])
        self.assertIn('+256 700 123 456', contacts['phones'])

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


class EventRegistrationTests(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username='event_admin',
            password='secret1234',
            is_staff=True,
        )

    def test_registration_admin_requires_staff_user(self):
        response = self.client.get(reverse('registration_admin'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_can_filter_and_verify_registration(self):
        booking = EventBooking.objects.create(
            booking_ref='BOOK-ADMIN1',
            full_name='Peter Kintu',
            phone='0789746493',
            email='peter@example.com',
            ticket_type='CEO',
            transaction_id='1982736450',
        )
        self.client.force_login(self.staff_user)

        response = self.client.get(reverse('registration_admin'), {'status': 'pending', 'ticket_type': 'CEO'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Peter Kintu')
        self.assertContains(response, '1982736450')

        response = self.client.post(reverse('verify_registration', args=[booking.booking_ref]))
        self.assertEqual(response.status_code, 302)
        booking.refresh_from_db()
        self.assertTrue(booking.is_verified)

    def test_staff_can_delete_registration(self):
        booking = EventBooking.objects.create(
            booking_ref='BOOK-DELETE1',
            full_name='Attendee Cancelled',
            phone='0789746493',
            email='cancelled@example.com',
            ticket_type='FREE',
            is_verified=True,
        )
        self.client.force_login(self.staff_user)

        response = self.client.post(reverse('delete_registration', args=[booking.booking_ref]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventBooking.objects.filter(booking_ref='BOOK-DELETE1').exists())

    def test_free_registration_is_confirmed_and_redirects_to_status(self):
        response = self.client.post(reverse('launch_registration'), {
            'full_name': 'Amina Nakato',
            'phone': '0789746493',
            'email': 'amina@example.com',
            'ticket_type': 'FREE',
        })

        booking = EventBooking.objects.get()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('registration_status', args=[booking.booking_ref]))
        self.assertTrue(booking.is_verified)

        status_response = self.client.get(response.url)
        self.assertContains(status_response, 'Download registration')
        self.assertNotContains(status_response, 'Register another attendee')
        self.assertContains(status_response, booking.booking_ref)

        download_response = self.client.get(reverse('download_registration', args=[booking.booking_ref]))
        self.assertEqual(download_response.status_code, 200)
        self.assertIn(booking.booking_ref.encode(), download_response.content)
        self.assertContains(download_response, 'Share')
        self.assertContains(download_response, 'WhatsApp')
        self.assertContains(download_response, 'Africana AI')
        self.assertIn('attachment;', download_response['Content-Disposition'])

    def test_same_name_cannot_register_multiple_times(self):
        registration = {
            'full_name': 'Same Attendee',
            'phone': '0789746493',
            'email': 'same@example.com',
            'ticket_type': 'FREE',
        }
        first = self.client.post(reverse('launch_registration'), registration)
        second = self.client.post(reverse('launch_registration'), registration)

        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(EventBooking.objects.filter(full_name='Same Attendee').count(), 1)

    def test_free_registration_has_receipt_and_unverified_ceo_has_no_card(self):
        booking = EventBooking.objects.create(
            booking_ref='BOOK-CARDTEST', full_name='Card Test', phone='0700000000',
            email='card@example.com', ticket_type='CEO', transaction_id='MOMO-1',
        )
        card_response = self.client.get(reverse('download_ceo_card', args=[booking.booking_ref]))
        self.assertEqual(card_response.status_code, 404)

    def test_verified_ceo_can_download_personalized_card(self):
        booking = EventBooking.objects.create(
            booking_ref='BOOK-CARDOK1', full_name='Card Holder', phone='0700000000',
            email='holder@example.com', ticket_type='CEO', transaction_id='MOMO-2',
        )
        self.client.force_login(self.staff_user)
        self.client.post(reverse('verify_registration', args=[booking.booking_ref]))
        booking.refresh_from_db()

        card_response = self.client.get(reverse('download_ceo_card', args=[booking.booking_ref]))

        self.assertEqual(card_response.status_code, 200)
        self.assertEqual(card_response['Content-Type'], 'image/png')
        self.assertIn(b'\x89PNG', card_response.content[:8])
        self.assertEqual(booking.founding_member_number, 1)

    def test_ceo_registration_requires_payment_evidence(self):
        response = self.client.post(reverse('launch_registration'), {
            'full_name': 'Peter Kintu',
            'phone': '0789746493',
            'email': 'peter@example.com',
            'ticket_type': 'CEO',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(EventBooking.objects.exists())

    def test_ceo_registration_with_transaction_id_is_pending(self):
        self.client.post(reverse('launch_registration'), {
            'full_name': 'Peter Kintu',
            'phone': '0789746493',
            'email': 'peter@example.com',
            'ticket_type': 'CEO',
            'transaction_id': '1982736450',
        })

        booking = EventBooking.objects.get()
        self.assertFalse(booking.is_verified)
        self.assertEqual(booking.transaction_id, '1982736450')

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

    @patch.dict('os.environ', {
        'PESAPAL_CONSUMER_KEY': 'live-key',
        'PESAPAL_CONSUMER_SECRET': 'live-secret',
    })
    @patch('users.views._pesapal_access_token', return_value='bearer-token-xyz')
    @patch('users.views.requests.post')
    def test_submit_order_uses_bearer_token_auth(self, mock_post, mock_access_token):
        mock_post.return_value = SimpleNamespace(
            status_code=200,
            ok=True,
            json=lambda: {'order_tracking_id': 'tracking-456'},
        )

        _pesapal_request('post', 'Transactions/SubmitOrderRequest', json_data={'id': 'order-001'})

        mock_post.assert_called_once_with(
            'https://pay.pesapal.com/v3/api/Transactions/SubmitOrderRequest',
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Authorization': 'Bearer bearer-token-xyz',
            },
            json={'id': 'order-001'},
            timeout=20,
        )


class UserRegistrationEmailTests(TestCase):
    def test_registration_sends_welcome_email(self):
        user = User.objects.create_user(
            username='amina',
            email='amina@example.com',
            password='Violet!River7Stone#',
        )

        _send_welcome_email(user)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['amina@example.com'])
        self.assertEqual(mail.outbox[0].from_email, 'Africana AI <info@africanaai.info>')
        self.assertIn('Welcome to Africana AI', mail.outbox[0].subject)

    def test_notification_task_sends_using_default_sender(self):
        result = send_user_notification_task.run(
            'amina@example.com',
            'System notification',
            'Your Africana AI notification is ready.',
        )

        self.assertTrue(result)
        self.assertEqual(mail.outbox[0].to, ['amina@example.com'])
        self.assertEqual(mail.outbox[0].from_email, 'Africana AI <info@africanaai.info>')


class DailyDigestCommandTests(TestCase):
    def test_daily_digest_sends_only_to_active_users_with_email(self):
        User.objects.create_user(username='active', email='active@example.com', is_active=True)
        User.objects.create_user(username='inactive', email='inactive@example.com', is_active=False)
        User.objects.create_user(username='no_email', email='', is_active=True)

        call_command('send_daily_digest')

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['active@example.com'])

    def test_daily_digest_continues_after_a_delivery_failure(self):
        User.objects.create_user(username='first', email='first@example.com', is_active=True)
        User.objects.create_user(username='second', email='second@example.com', is_active=True)

        with patch('users.management.commands.send_daily_digest.send_mail', side_effect=[
            RuntimeError('SMTP unavailable'),
            1,
        ]) as mock_send_mail:
            call_command('send_daily_digest')

        self.assertEqual(mock_send_mail.call_count, 2)
        self.assertEqual(len(mail.outbox), 0)


class NylonIntegrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='pesapal_user',
            email='pesapal@example.com',
            password='secret1234',
        )

    @patch('users.views.collect_payment')
    def test_start_checkout_activates_subscription_after_nylon_success(self, collect_payment):
        collect_payment.return_value = SimpleNamespace(
            reference='550e8400-e29b-41d4-a716-446655440000',
            transaction_id='transaction-123',
            status='paid',
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse('users:nylon_start_checkout'),
            {'phone': '+256700000000'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('users:nylon_callback'), response.url)
        payment = PesapalPayment.objects.get(user=self.user)
        subscription = UserSubscription.objects.get(user=self.user)
        self.assertEqual(payment.status, 'PAID')
        self.assertEqual(payment.tracking_id, 'transaction-123')
        self.assertTrue(subscription.is_active)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, '+256700000000')

    def test_legacy_pesapal_ipn_is_disabled(self):
        response = self.client.post(
            reverse('users:pesapal_ipn'),
        )

        self.assertEqual(response.status_code, 410)

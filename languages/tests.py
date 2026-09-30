import base64
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import views
from .models import JobAlert, JobAlertDelivery, JobPost
from .tasks import enqueue_job_alerts, send_job_alert_email


class ClientIpTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def test_uses_first_public_address_in_forwarded_header(self):
		request = self.factory.get(
			'/', HTTP_X_FORWARDED_FOR='8.8.8.8, 10.0.0.4'
		)

		self.assertEqual(views.get_client_ip(request), '8.8.8.8')

	def test_rejects_private_forwarded_address_instead_of_proxy_fallback(self):
		request = self.factory.get(
			'/',
			HTTP_X_FORWARDED_FOR='10.0.0.4, 8.8.8.8',
			REMOTE_ADDR='1.1.1.1',
		)

		self.assertEqual(views.get_client_ip(request), '')

	def test_rejects_loopback_remote_address(self):
		request = self.factory.get('/', REMOTE_ADDR='127.0.0.1')

		self.assertEqual(views.get_client_ip(request), '')

	@patch.object(views, 'get_external_session')
	@patch.object(views, 'get_cached_result', return_value=None)
	@patch.object(views.cache, 'get', return_value=None)
	@patch.object(views, 'get_client_ip', return_value='')
	def test_skips_careerjet_request_without_public_client_ip(
		self, _get_client_ip, _cache_get, _get_cached_result, get_external_session
	):
		request = self.factory.get('/jobs', HTTP_USER_AGENT='test-agent')

		with patch.object(views, 'CAREERJET_API_ENABLED', True):
			result = views.fetch_careerjet_data(request, 'engineer')

		self.assertEqual(result, [])
		get_external_session.assert_not_called()
	def test_sends_required_query_metadata_and_basic_auth(self):
		request = self.factory.get(
			'/jobs',
			HTTP_X_FORWARDED_FOR='8.8.8.8',
			HTTP_USER_AGENT='test-agent',
		)
		session = Mock()
		session.get.return_value = Mock(status_code=403, text='test response')

		with (
			patch.object(views, 'CAREERJET_API_ENABLED', True),
			patch.object(views, 'CAREERJET_API_KEY', 'test-api-key'),
			patch.object(views, 'get_cached_result', return_value=None),
			patch.object(views.cache, 'get', side_effect=[None, []]),
			patch.object(views, 'get_external_session', return_value=session),
			patch.object(views.time, 'sleep'),
		):
			result = views.fetch_careerjet_data(request, 'engineer')

		self.assertEqual(result, [])
		request_url, request_options = session.get.call_args
		self.assertEqual(request_url[0], 'https://search.api.careerjet.net/v4/query')
		self.assertEqual(request_options['params']['user_ip'], '8.8.8.8')
		self.assertEqual(request_options['params']['user_agent'], 'test-agent')
		self.assertEqual(
			session.headers.update.call_args.args[0]['Authorization'],
			'Basic ' + base64.b64encode(b'test-api-key:').decode(),
		)

	@patch.object(views, 'get_external_session')
	@patch.object(views, 'get_cached_result', return_value=None)
	@patch.object(views.cache, 'get', return_value=None)
	@patch.object(views, 'get_client_ip', return_value='8.8.8.8')
	def test_skips_careerjet_request_without_user_agent(
		self, _get_client_ip, _cache_get, _get_cached_result, get_external_session
	):
		request = self.factory.get('/jobs')

		with patch.object(views, 'CAREERJET_API_ENABLED', True):
			result = views.fetch_careerjet_data(request, 'engineer')

		self.assertEqual(result, [])
		get_external_session.assert_not_called()


@override_settings(
	EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
	DEFAULT_FROM_EMAIL='alerts@example.com',
	DEFAULT_DOMAIN='example.com',
)
class JobAlertTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username='jobseeker',
			email='jobseeker@example.com',
			password='test-password',
		)
		self.client.force_login(self.user)

	def create_job(self, **overrides):
		values = {
			'job_category': 'luganda',
			'post_content': 'Data Engineer',
			'required_skills': 'Python and SQL',
			'recruiter_name': 'Example Employer',
			'recruiter_location': 'Kampala, Uganda',
			'valid_through': timezone.now() + timedelta(days=5),
			'is_validated': True,
			'is_external': False,
		}
		values.update(overrides)
		return JobPost.objects.create(**values)

	def test_user_can_save_pause_resume_and_delete_alert(self):
		response = self.client.post(
			reverse('languages:save_job_alert'),
			{
				'role_query': 'Data Engineer',
				'location': 'Kampala',
				'category': 'luganda',
			},
		)

		self.assertEqual(response.status_code, 302)
		alert = JobAlert.objects.get(user=self.user)
		self.assertEqual(alert.role_query, 'Data Engineer')
		self.assertEqual(alert.location, 'Kampala')

		self.client.post(reverse('languages:save_job_alert'), {
			'role_query': 'Data Engineer',
			'location': 'Kampala',
			'category': 'luganda',
		})
		self.assertEqual(JobAlert.objects.filter(user=self.user).count(), 1)

		self.client.post(reverse('languages:toggle_job_alert', args=[alert.pk]))
		alert.refresh_from_db()
		self.assertFalse(alert.is_active)
		self.client.post(reverse('languages:toggle_job_alert', args=[alert.pk]))
		alert.refresh_from_db()
		self.assertTrue(alert.is_active)
		self.client.post(reverse('languages:delete_job_alert', args=[alert.pk]))
		self.assertFalse(JobAlert.objects.filter(pk=alert.pk).exists())

	def test_alert_page_renders_creation_form_and_saved_search(self):
		JobAlert.objects.create(user=self.user, role_query='Data analyst', location='Gulu')

		response = self.client.get(reverse('languages:job_alerts'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Create job alert')
		self.assertContains(response, 'Data analyst')

	def test_alert_controls_only_change_the_owner_alerts(self):
		other_user = get_user_model().objects.create_user(
			username='another-user',
			email='another@example.com',
			password='test-password',
		)
		alert = JobAlert.objects.create(user=other_user, role_query='Designer')

		response = self.client.post(reverse('languages:delete_job_alert', args=[alert.pk]))

		self.assertEqual(response.status_code, 404)
		self.assertTrue(JobAlert.objects.filter(pk=alert.pk).exists())

	def test_alert_requires_at_least_one_criterion_and_valid_category(self):
		self.client.post(reverse('languages:save_job_alert'), {})
		self.client.post(reverse('languages:save_job_alert'), {
			'role_query': 'Engineer',
			'category': 'not-a-category',
		})
		self.assertFalse(JobAlert.objects.exists())

	def test_only_matching_active_local_unexpired_jobs_are_queued(self):
		alert = JobAlert.objects.create(
			user=self.user,
			role_query='data engineer',
			location='kampala',
			category='luganda',
		)
		JobAlert.objects.create(user=self.user, role_query='Paused role', is_active=False)
		matching_job = self.create_job()
		self.create_job(post_content='Designer', required_skills='Illustration')
		self.create_job(is_external=True)
		self.create_job(valid_through=timezone.now() - timedelta(days=1))
		self.create_job(is_validated=False)

		with patch('languages.tasks.send_job_alert_email.delay') as send_alert:
			queued = enqueue_job_alerts(matching_job.pk)

		self.assertEqual(queued, 1)
		send_alert.assert_called_once_with(alert.pk, matching_job.pk)

	def test_email_links_to_job_and_management_and_is_deduplicated(self):
		alert = JobAlert.objects.create(user=self.user, role_query='Data Engineer')
		job = self.create_job()

		self.assertTrue(send_job_alert_email(alert.pk, job.pk))
		self.assertTrue(send_job_alert_email(alert.pk, job.pk))

		from django.core import mail
		self.assertEqual(len(mail.outbox), 1)
		self.assertIn(reverse('languages:job_post_detail', args=[job.pk]), mail.outbox[0].body)
		self.assertIn(reverse('languages:job_alerts'), mail.outbox[0].body)
		self.assertTrue(JobAlertDelivery.objects.get(alert=alert, job=job).sent_at)

	def test_job_creation_and_validation_transition_schedule_matching(self):
		with patch('languages.signals.enqueue_job_alerts.delay') as enqueue:
			with self.captureOnCommitCallbacks(execute=True):
				self.create_job()
			enqueue.assert_called_once()

		with patch('languages.signals.enqueue_job_alerts.delay') as enqueue:
			with self.captureOnCommitCallbacks(execute=True):
				job = self.create_job(is_validated=False)
				enqueue.assert_not_called()
				job.is_validated = True
				job.save(update_fields=['is_validated'])
			enqueue.assert_called_once_with(job.pk)

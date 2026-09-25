from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from . import views


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

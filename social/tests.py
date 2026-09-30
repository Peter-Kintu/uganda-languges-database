from django.test import TestCase
from django.urls import reverse


class FeedCacheTests(TestCase):
	def test_feed_renders_with_the_pages_cache_alias(self):
		response = self.client.get(reverse('social:social_feed'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Social Feed')

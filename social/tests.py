from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BusinessReel


class FeedCacheTests(TestCase):
	def test_feed_renders_with_the_pages_cache_alias(self):
		response = self.client.get(reverse('social:social_feed'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Social Feed')


class PublicReelDetailTests(TestCase):
	def test_public_reel_page_includes_full_caption_in_server_response(self):
		author = get_user_model().objects.create_user(
			username='public-post-author',
			password='test-password',
		)
		caption = 'First paragraph of the post.\n\nSecond paragraph with the complete public text.'
		reel = BusinessReel.objects.create(author=author, caption=caption)

		response = self.client.get(
			reverse('social:reel_detail', kwargs={'reel_id': reel.id})
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'First paragraph of the post.')
		self.assertContains(response, 'Second paragraph with the complete public text.')
		self.assertContains(
			response,
			f'<link rel="canonical" href="https://www.africanaai.info/social/reel/{reel.id}/">',
			html=True,
		)

	def test_inactive_reels_are_not_publicly_accessible(self):
		author = get_user_model().objects.create_user(
			username='inactive-post-author',
			password='test-password',
		)
		reel = BusinessReel.objects.create(
			author=author,
			caption='This post is not public.',
			is_active=False,
		)

		response = self.client.get(
			reverse('social:reel_detail', kwargs={'reel_id': reel.id})
		)

		self.assertEqual(response.status_code, 404)

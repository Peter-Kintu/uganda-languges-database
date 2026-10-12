from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from .models import BusinessReel, MerchantIdentityVerification, SocialProfile


def make_test_id_image(filename):
	buffer = BytesIO()
	Image.new('RGB', (20, 20), color='blue').save(buffer, format='JPEG')
	return SimpleUploadedFile(filename, buffer.getvalue(), content_type='image/jpeg')


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


class MerchantIdentityVerificationTests(TestCase):
	def setUp(self):
		self.identity_storage = MerchantIdentityVerification._meta.get_field('id_front_image').storage
		self.original_storage_location = self.identity_storage._location
		self.original_cached_location = self.identity_storage.__dict__.pop('location', None)
		self.test_storage_directory = tempfile.TemporaryDirectory()
		self.identity_storage._location = self.test_storage_directory.name
		self.identity_storage.__dict__.pop('location', None)

	def tearDown(self):
		for verification in MerchantIdentityVerification.objects.all():
			verification.id_front_image.delete(save=False)
			verification.id_back_image.delete(save=False)
		self.identity_storage._location = self.original_storage_location
		self.identity_storage.__dict__.pop('location', None)
		if self.original_cached_location is not None:
			self.identity_storage.__dict__['location'] = self.original_cached_location
		self.test_storage_directory.cleanup()

	def test_identity_documents_are_submitted_privately_and_admin_only(self):
		user = get_user_model().objects.create_user(
			username='id-owner',
			email='owner@example.com',
			password='test-password',
		)
		self.client.force_login(user)

		profile_response = self.client.get(reverse('users:profile'))
		self.assertEqual(profile_response.status_code, 200)
		self.assertContains(profile_response, 'name="national_id_number"')
		self.assertContains(profile_response, 'name="id_front_image"')
		self.assertContains(profile_response, 'name="id_back_image"')
		self.assertContains(profile_response, 'Submit verification')
		self.assertContains(profile_response, 'background-color: #007c83 !important')

		response = self.client.post(reverse('eshop:submit_verification'), {
			'national_id_number': 'cf 12345678 abcd',
			'business_registration_ref': 'REG-123',
			'id_front_image': make_test_id_image('front.jpg'),
			'id_back_image': make_test_id_image('back.jpg'),
		})

		self.assertEqual(response.status_code, 302)
		profile = SocialProfile.objects.get(user=user)
		verification = MerchantIdentityVerification.objects.get(social_profile=profile)
		self.assertEqual(verification.national_id_number, 'CF12345678ABCD')
		self.assertEqual(profile.verification_status, 'pending')
		self.assertEqual(profile.business_registration_ref, 'REG-123')
		self.assertNotIn(verification.national_id_number, response.content.decode())
		profile_response = self.client.get(reverse('users:profile'))
		self.assertNotContains(profile_response, verification.national_id_number)
		self.assertNotContains(profile_response, 'name="national_id_number"')

		private_url = verification.id_front_image.url
		self.assertEqual(self.client.get(private_url).status_code, 404)
		front_name = verification.id_front_image.name
		back_name = verification.id_back_image.name
		self.assertTrue(verification.id_front_image.storage.exists(front_name))
		self.assertTrue(verification.id_back_image.storage.exists(back_name))

		document_url = reverse(
			'admin:social_merchantidentityverification_document',
			args=(verification.pk, 'front'),
		)
		self.assertEqual(self.client.get(document_url).status_code, 302)

		staff = get_user_model().objects.create_user(
			username='unprivileged-staff',
			password='test-password',
			is_staff=True,
		)
		staff_client = self.client_class(raise_request_exception=False)
		staff_client.force_login(staff)
		self.assertEqual(staff_client.get(document_url).status_code, 403)

		admin = get_user_model().objects.create_superuser(
			username='identity-admin',
			email='admin@example.com',
			password='test-password',
		)
		admin_client = self.client_class()
		admin_client.force_login(admin)
		admin_response = admin_client.get(document_url)
		self.assertEqual(admin_response.status_code, 200)
		self.assertEqual(admin_response['Content-Disposition'].split(';')[0], 'attachment')
		self.assertIn('private, no-store', admin_response['Cache-Control'])
		self.assertEqual(b''.join(admin_response.streaming_content), make_test_id_image('expected.jpg').read())
		admin_response.close()
		verification.delete()
		self.assertFalse(self.identity_storage.exists(front_name))
		self.assertFalse(self.identity_storage.exists(back_name))

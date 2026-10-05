from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import Mock, patch

from languages.models import JobPost

from .models import (
	Community, CommunityChannel, CommunityMessage, CommunityModerationRule,
	CommunityRole, Connection, FeedImpression, Like, Post,
	Message,
)
from .views import _build_hybrid_feed, _build_market_feed_items, _feed_insert_positions, translate_smart


User = get_user_model()


class HybridFeedTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='feed_user', password='secret123')
		self.followed_user = User.objects.create_user(username='followed_user', password='secret123')
		self.popular_user = User.objects.create_user(username='popular_user', password='secret123')
		self.investor = User.objects.create_user(
			username='investor_user',
			password='secret123',
			user_type='investor',
			is_approved=True,
		)

	def test_established_feed_prioritizes_followed_and_deduplicates_buckets(self):
		Connection.objects.create(sender=self.user, receiver=self.followed_user, status='accepted')
		followed_post = Post.objects.create(author=self.followed_user, content='Followed update')
		popular_post = Post.objects.create(author=self.popular_user, content='Popular update')
		useful_post = Post.objects.create(author=self.investor, content='Useful announcement')
		likers = [User.objects.create_user(username=f'liker_{index}', password='secret123') for index in range(5)]
		Like.objects.bulk_create([
			Like(post=popular_post, user=liker) for liker in likers
		])

		feed = _build_hybrid_feed(self.user, feed_seed='test-seed')

		self.assertEqual(feed[0], followed_post)
		self.assertIn(popular_post, feed)
		self.assertIn(useful_post, feed)
		self.assertEqual(len(feed), len({post.id for post in feed}))

	def test_new_user_receives_discovery_content_without_follows(self):
		popular_post = Post.objects.create(author=self.popular_user, content='Popular update')
		useful_post = Post.objects.create(author=self.investor, content='Useful announcement')
		likers = [User.objects.create_user(username=f'new_liker_{index}', password='secret123') for index in range(5)]
		Like.objects.bulk_create([
			Like(post=popular_post, user=liker) for liker in likers
		])

		feed = _build_hybrid_feed(self.user, feed_seed='test-seed')

		self.assertTrue(feed)
		self.assertEqual(feed[0], popular_post)
		self.assertIn(useful_post, feed)

	def test_feed_seed_changes_order_without_changing_membership(self):
		posts = [
			Post.objects.create(author=self.popular_user, content=f'Post {index}')
			for index in range(6)
		]

		first_feed = _build_hybrid_feed(self.user, feed_seed='first-seed')
		second_feed = _build_hybrid_feed(self.user, feed_seed='second-seed')

		self.assertEqual({post.id for post in first_feed}, {post.id for post in second_feed})
		self.assertNotEqual([post.id for post in first_feed], [post.id for post in second_feed])

	def test_market_feed_handles_missing_profile_fields(self):
		request = RequestFactory().get('/hotel/')
		request.user = self.user
		request.session = {}

		products, jobs = _build_market_feed_items(request)

		self.assertIsInstance(products, list)
		self.assertIsInstance(jobs, list)

	def test_market_feed_falls_back_when_history_has_no_job_match(self):
		job = JobPost.objects.create(
			posted_by=self.popular_user,
			post_content='Available opportunity',
			required_skills='Communication',
			timestamp=timezone.now(),
			is_validated=True,
		)
		request = RequestFactory().get('/hotel/')
		request.user = self.user
		request.session = {'job_search_history': [{'query': 'nonexistent-role', 'location': ''}]}

		_, jobs = _build_market_feed_items(request)

		self.assertIn(job, jobs)

	def test_feed_impression_counts_once_per_viewer_session_item(self):
		post = Post.objects.create(author=self.popular_user, content='Visible update')
		self.client.force_login(self.user)

		first = self.client.post('/hotel/record-impression/', {
			'content_type': 'post', 'object_id': post.id,
		})
		second = self.client.post('/hotel/record-impression/', {
			'content_type': 'post', 'object_id': post.id,
		})

		post.refresh_from_db()
		self.assertTrue(first.json()['counted'])
		self.assertFalse(second.json()['counted'])
		self.assertEqual(post.impressions, 1)
		self.assertEqual(FeedImpression.objects.count(), 1)

	def test_like_post_toggles_like_and_returns_count(self):
		post = Post.objects.create(author=self.popular_user, content='Likeable update')
		self.client.force_login(self.user)

		with patch('hotel.views.invalidate_hotel_feed_cache') as invalidate:
			first = self.client.post(f'/hotel/like-post/{post.id}/')
			second = self.client.post(f'/hotel/like-post/{post.id}/')

		self.assertEqual(first.json()['likes_count'], 1)
		self.assertEqual(second.json()['likes_count'], 0)
		invalidate.assert_not_called()

	@patch('hotel.views.rebuild_hotel_feed_cache.apply_async', side_effect=RuntimeError('broker unavailable'))
	@patch('hotel.views.cache.delete_many', side_effect=ConnectionError('cache unavailable'))
	def test_feed_cache_invalidation_is_non_blocking_when_redis_is_unavailable(
		self, _delete_many, _enqueue
	):
		with self.assertLogs('hotel.views', level='ERROR'):
			from .views import invalidate_hotel_feed_cache

			invalidate_hotel_feed_cache()
		_enqueue.assert_called_once_with(
			args=('hotel:feed:public:all', 20),
			retry=False,
		)

	def test_ajax_feed_uses_reaction_control_markup(self):
		post = Post.objects.create(author=self.popular_user, content='Loaded update')
		self.client.force_login(self.user)

		response = self.client.get('/hotel/?format=json', HTTP_X_REQUESTED_WITH='XMLHttpRequest')

		self.assertEqual(response.status_code, 200)
		html = response.json()['html']
		self.assertIn('class="post-action reaction-like"', html)
		self.assertIn('class="post-action reaction-more"', html)
		self.assertIn(
			f'href="{reverse("hotel:public_profile", args=[post.author_id])}"',
			html,
		)

	def test_initial_feed_links_discoverable_author_names_to_public_profiles(self):
		post = Post.objects.create(author=self.popular_user, content='Public author update')
		self.client.force_login(self.user)

		response = self.client.get('/hotel/')

		self.assertEqual(response.status_code, 200)
		self.assertContains(
			response,
			reverse('hotel:public_profile', args=[post.author_id]),
		)

	def test_initial_feed_does_not_link_hidden_author_profile(self):
		hidden_author = User.objects.create_user(
			username='hidden_author',
			password='secret123',
			discoverable_by_handle=False,
		)
		Post.objects.create(author=hidden_author, content='Hidden author update')
		self.client.force_login(self.user)

		response = self.client.get('/hotel/')

		self.assertEqual(response.status_code, 200)
		self.assertNotContains(
			response,
			reverse('hotel:public_profile', args=[hidden_author.pk]),
		)

	def test_market_and_job_positions_rotate_with_feed_seed(self):
		first_products, first_job = _feed_insert_positions(20, 'first-seed')
		second_products, second_job = _feed_insert_positions(20, 'second-seed')

		self.assertEqual(len(first_products), 3)
		self.assertEqual(len(second_products), 3)
		self.assertNotEqual(first_job, second_job)

	@patch('hotel.views._safe_cache_get', return_value=None)
	@patch('hotel.views.requests.post')
	def test_translation_retries_when_configured_gemini_model_is_unavailable(self, post, _cache_get):
		unavailable = Mock(status_code=404)
		available = Mock(status_code=200)
		available.json.return_value = {
			'candidates': [{'content': {'parts': [{'text': 'Oli otya'}]}}]
		}
		post.side_effect = [unavailable, available]

		with patch('hotel.views.GEMINI_API_KEY', 'test-key'), patch(
			'hotel.views.GEMINI_TRANSLATION_FALLBACK_MODELS',
			('retired-model', 'working-model'),
		):
			translated = translate_smart('How are you?', 'lug')

		self.assertEqual(translated, 'Oli otya')
		self.assertEqual(post.call_count, 2)
		self.assertIn('/retired-model:generateContent', post.call_args_list[0].args[0])
		self.assertIn('/working-model:generateContent', post.call_args_list[1].args[0])

	@patch('hotel.views._safe_cache_get', return_value=None)
	@patch('hotel.views.requests.post')
	def test_nllb_uses_self_hosted_language_code_and_optional_auth(self, post, _cache_get):
		response = Mock(status_code=200)
		response.json.return_value = {'translated_text': 'Ki kati?'}
		post.return_value = response

		with patch('hotel.views.GEMINI_API_KEY', None), patch(
			'hotel.views.SUNBIRD_API_KEY', None,
		), patch('hotel.views.NLLB_URL', 'https://nllb.example/translate'), patch(
			'hotel.views.NLLB_API_KEY', 'nllb-test-key',
		), patch('hotel.views._google_translate', return_value=None):
			translated = translate_smart('How are you?', 'lg')

		self.assertEqual(translated, 'Ki kati?')
		request = post.call_args.kwargs
		self.assertEqual(request['json']['target'], 'lg')
		self.assertEqual(request['headers']['Authorization'], 'Bearer nllb-test-key')


class PublicMemberProfileTests(TestCase):
	def setUp(self):
		self.member = User.objects.create_user(
			username='public_member',
			password='secret123',
			first_name='Public',
			last_name='Member',
			email='private@example.com',
			phone='+256700000000',
			headline='Community builder',
			about='I support local founders.',
			location='Kampala',
		)

	def test_public_profile_is_anonymous_and_excludes_private_account_details(self):
		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Public Member')
		self.assertContains(response, '@public_member')
		self.assertContains(response, 'Community builder')
		self.assertContains(response, 'I support local founders.')
		self.assertContains(response, 'Kampala')
		self.assertNotContains(response, 'private@example.com')
		self.assertNotContains(response, '+256700000000')
		self.assertNotContains(response, 'Edit Profile')
		self.assertContains(response, 'Sign in to connect')

	def test_public_profile_shows_professional_history_education_skills_and_activity(self):
		from datetime import date
		from users.models import Education, Experience, Skill

		Experience.objects.create(
			user=self.member,
			title='Product Designer',
			company_name='Cedar Studio',
			start_date=date(2022, 1, 1),
			description='Led product research and interface design.',
		)
		Education.objects.create(
			user=self.member,
			institution='Makerere University',
			degree='Bachelor of Design',
			field_of_study='Industrial Design',
			start_date=date(2018, 1, 1),
			end_date=date(2021, 12, 1),
		)
		Skill.objects.create(name='Product Design', user=self.member)
		Post.objects.create(author=self.member, content='Sharing a recent design project.')

		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Experience')
		self.assertContains(response, 'Product Designer')
		self.assertContains(response, 'Cedar Studio')
		self.assertContains(response, 'Education')
		self.assertContains(response, 'Makerere University')
		self.assertContains(response, 'Skills')
		self.assertContains(response, 'Product Design')
		self.assertContains(response, 'Recent activity')
		self.assertContains(response, 'Sharing a recent design project.')

	def test_signed_in_profile_shows_follow_and_privacy_aware_message_actions(self):
		viewer = User.objects.create_user(username='profile_viewer', password='secret123')
		self.client.force_login(viewer)

		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Follow')
		self.assertContains(response, 'Message')
		self.assertContains(response, reverse('hotel:conversation', args=[self.member.pk]))

		self.member.direct_message_privacy = 'connections'
		self.member.save(update_fields=['direct_message_privacy'])
		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))
		self.assertNotContains(response, reverse('hotel:conversation', args=[self.member.pk]))
		self.assertContains(response, 'Follow to message')
		self.assertContains(response, reverse('hotel:follow_user', args=[self.member.pk]))

		from .models import Connection
		Connection.objects.create(sender=viewer, receiver=self.member, status='accepted')
		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))
		self.assertContains(response, reverse('hotel:conversation', args=[self.member.pk]))
		self.assertContains(response, reverse('hotel:unfollow_user', args=[self.member.pk]))
		self.assertEqual(
			self.client.get(reverse('hotel:conversation', args=[self.member.pk])).status_code,
			200,
		)
		conversation_response = self.client.get(reverse('hotel:conversation', args=[self.member.pk]))
		self.assertContains(conversation_response, 'View profile')
		self.assertContains(conversation_response, 'Write a message...')
		self.assertContains(conversation_response, 'flex-col gap-2 sm:flex-row')

		self.member.direct_message_privacy = 'nobody'
		self.member.save(update_fields=['direct_message_privacy'])
		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))
		self.assertNotContains(response, reverse('hotel:conversation', args=[self.member.pk]))
		self.assertContains(response, 'Not accepting messages')
		self.assertRedirects(
			self.client.get(reverse('hotel:conversation', args=[self.member.pk])),
			reverse('hotel:public_profile', args=[self.member.pk]),
		)

	def test_non_discoverable_member_is_not_public(self):
		self.member.discoverable_by_handle = False
		self.member.save(update_fields=['discoverable_by_handle'])

		response = self.client.get(reverse('hotel:public_profile', args=[self.member.pk]))

		self.assertEqual(response.status_code, 404)

	def test_feed_suggestions_only_include_discoverable_active_users(self):
		viewer = User.objects.create_user(username='feed_viewer', password='secret123')
		hidden_member = User.objects.create_user(
			username='hidden_member',
			password='secret123',
			discoverable_by_handle=False,
		)
		inactive_member = User.objects.create_user(
			username='inactive_member',
			password='secret123',
			is_active=False,
		)
		self.client.force_login(viewer)

		response = self.client.get('/hotel/')

		self.assertEqual(response.status_code, 200)
		suggested_users = response.context['all_users']
		self.assertIn(self.member, suggested_users)
		self.assertNotIn(hidden_member, suggested_users)
		self.assertNotIn(inactive_member, suggested_users)


class CommunityArchitectureTests(TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(username='community_owner', password='secret123')
		self.member = User.objects.create_user(username='community_member', password='secret123')
		self.community = Community.objects.create(
			name='Kampala Builders', creator=self.owner, description='Build together'
		)
		self.community.members.add(self.owner, self.member)
		self.client.force_login(self.owner)

	def test_community_page_provisions_general_channel_and_roles(self):
		response = self.client.get(f'/hotel/community/{self.community.id}/')

		self.assertEqual(response.status_code, 200)
		self.assertTrue(CommunityChannel.objects.filter(community=self.community, slug='general').exists())
		self.assertTrue(CommunityRole.objects.filter(community=self.community, name='Admin').exists())

	def test_only_moderator_can_create_channel(self):
		self.client.force_login(self.member)
		response = self.client.post(f'/hotel/community/{self.community.id}/channels/create/', {'name': 'Jobs'})

		self.assertEqual(response.status_code, 403)
		self.client.force_login(self.owner)
		response = self.client.post(f'/hotel/community/{self.community.id}/channels/create/', {'name': 'Jobs'})

		self.assertEqual(response.status_code, 200)
		self.assertTrue(CommunityChannel.objects.filter(community=self.community, slug='jobs').exists())

	def test_moderation_holds_matching_content_out_of_visible_messages(self):
		CommunityModerationRule.objects.create(community=self.community, phrase='fake giveaway', action='hold')
		response = self.client.post(
			f'/hotel/community/{self.community.id}/',
			{'content': 'This is a fake giveaway', 'channel': ''},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['status'], 'held')
		message = CommunityMessage.objects.get(community=self.community)
		self.assertEqual(message.moderation_status, 'held')
		self.assertFalse(CommunityMessage.objects.filter(community=self.community, moderation_status='visible').exists())

	def test_direct_message_privacy_blocks_unwanted_message(self):
		self.member.direct_message_privacy = 'nobody'
		self.member.save(update_fields=['direct_message_privacy'])
		response = self.client.post(f'/hotel/send_message/{self.member.id}/', {'content': 'Hello'})

		self.assertEqual(response.status_code, 403)

	def test_direct_ajax_attachment_returns_saved_message_metadata(self):
		attachment = SimpleUploadedFile('photo.png', b'not-a-real-image', content_type='image/png')
		response = self.client.post(
			f'/hotel/send_message/{self.member.id}/',
			{'content': 'See this', 'attachment': attachment},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
			HTTP_ACCEPT='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertTrue(response.json()['attachment_url'])
		self.assertEqual(Message.objects.count(), 1)

	def test_community_ajax_attachment_returns_saved_message_metadata(self):
		self.client.force_login(self.member)
		attachment = SimpleUploadedFile('clip.mp4', b'not-a-real-video', content_type='video/mp4')
		response = self.client.post(
			f'/hotel/community/{self.community.id}/',
			{'content': 'Watch this', 'attachment': attachment, 'channel': ''},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
			HTTP_ACCEPT='application/json',
		)

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.assertTrue(response.json()['attachment_url'])
		self.assertEqual(CommunityMessage.objects.count(), 1)

# Create your tests here.

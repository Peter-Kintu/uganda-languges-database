from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from .models import Connection, FeedImpression, Like, Post
from .views import _build_hybrid_feed, _build_market_feed_items, _feed_insert_positions


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

	def test_market_and_job_positions_rotate_with_feed_seed(self):
		first_products, first_job = _feed_insert_positions(20, 'first-seed')
		second_products, second_job = _feed_insert_positions(20, 'second-seed')

		self.assertEqual(len(first_products), 3)
		self.assertEqual(len(second_products), 3)
		self.assertNotEqual(first_job, second_job)

# Create your tests here.

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Connection, Like, Post
from .views import _build_hybrid_feed


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

# Create your tests here.

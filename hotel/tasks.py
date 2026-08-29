from celery import shared_task
from django.core.cache import cache
from .models import Post


@shared_task(bind=True)
def rebuild_hotel_feed_cache(self, cache_key='hotel:feed:public:all', limit=20):
    """Rebuild the cached public hotel feed from the database."""
    recent_posts = list(Post.objects.select_related('author').order_by('-created_at')[:limit])
    payload = [
        {
            'id': post.id,
            'author_id': post.author_id,
            'author_username': post.author.username,
            'content': post.content,
            'location': post.location,
            'created_at': post.created_at.isoformat() if hasattr(post.created_at, 'isoformat') else str(post.created_at),
        }
        for post in recent_posts
    ]
    cache.set(cache_key, payload, timeout=300)
    return {'status': 'ok', 'count': len(payload), 'cache_key': cache_key}


@shared_task(bind=True)
def warm_hotel_feed_cache(self):
    """Pre-warm cached public feed responses after heavy writes."""
    return rebuild_hotel_feed_cache.delay('hotel:feed:public:all', 20)

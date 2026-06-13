"""
YouTube Data API v3 Service for Africana AI Social Platform.
Manages video fetching, channel discovery, and content syndication.
"""

import os
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import logging

logger = logging.getLogger(__name__)


class YouTubeService:
    """
    Service wrapper for YouTube Data API v3.
    Handles video fetching, channel metadata, and quota management.
    """
    
    def __init__(self, api_key=None):
        """Initialize YouTube API client."""
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        if not self.api_key:
            raise ValueError("YOUTUBE_API_KEY not set in environment")
        
        # Use API key with discovery cache disabled to avoid oauth2client file_cache warnings
        self.youtube = build('youtube', 'v3', developerKey=self.api_key, cache_discovery=False)
        self.quota_units_used = 0
    
    def get_channel_info(self, channel_id):
        """
        Fetch channel metadata including name, description, and profile pic.
        
        Args:
            channel_id (str): YouTube Channel ID (e.g., UCxxxxxx)
            
        Returns:
            dict: Channel metadata or None if not found
        """
        try:
            request = self.youtube.channels().list(
                part='snippet,statistics',
                id=channel_id
            )
            response = request.execute()
            self.quota_units_used += 1
            
            if response['items']:
                channel = response['items'][0]
                return {
                    'channel_id': channel['id'],
                    'channel_name': channel['snippet']['title'],
                    'channel_url': f"https://www.youtube.com/channel/{channel['id']}",
                    'channel_thumbnail': channel['snippet']['thumbnails']['default']['url'],
                    'description': channel['snippet']['description'],
                    'subscriber_count': channel['statistics'].get('subscriberCount', 0),
                }
            return None
        except HttpError as e:
            logger.error(f"Error fetching channel {channel_id}: {e}")
            return None
    
    def get_latest_videos(self, channel_id, max_results=50, published_after=None):
        """
        Fetch latest videos from a channel.
        
        Args:
            channel_id (str): YouTube Channel ID
            max_results (int): Maximum videos to fetch (1-50)
            published_after (datetime): Optional - fetch only videos after this date
            
        Returns:
            list: List of video metadata dicts
        """
        try:
            # Format published_after for API Key usage (Z-normalized ISO) and keep query strictly public
            formatted_date = None
            if published_after:
                if hasattr(published_after, 'isoformat'):
                    # Strip fractional seconds and ensure trailing Z
                    formatted_date = published_after.isoformat().split('.')[0] + 'Z'
                else:
                    formatted_date = str(published_after)

            # Build public search parameters; omit publishedAfter when not provided
            search_params = {
                'part': 'snippet',
                'channelId': channel_id,
                'order': 'date',
                'type': 'video',
                'maxResults': min(max_results, 50),
            }
            if formatted_date:
                search_params['publishedAfter'] = formatted_date

            search_request = self.youtube.search().list(**search_params)
            search_response = search_request.execute()
            self.quota_units_used += 100
            if not search_response.get('items'):
                return []

            # Extract video IDs safely
            video_ids = [
                item.get('id', {}).get('videoId')
                for item in search_response.get('items', [])
                if item.get('id', {}).get('videoId')
            ]
            
            # Get detailed video stats
            videos_request = self.youtube.videos().list(
                part='snippet,statistics,contentDetails',
                id=','.join(video_ids)
            )
            videos_response = videos_request.execute()
            self.quota_units_used += 1
            videos = []
            for video in videos_response.get('items', []):
                # Parse duration (ISO 8601 format)
                duration = self._parse_duration(video['contentDetails']['duration'])
                
                video_data = {
                    'youtube_id': video['id'],
                    'title': video['snippet']['title'],
                    'description': video['snippet']['description'],
                    'thumbnail_url': video['snippet']['thumbnails'].get('high', {}).get('url', 
                                      video['snippet']['thumbnails'].get('default', {}).get('url')),
                    'youtube_url': f"https://www.youtube.com/watch?v={video['id']}",
                    'duration_seconds': duration,
                    'youtube_views': int(video['statistics'].get('viewCount', 0)),
                    'youtube_likes': int(video['statistics'].get('likeCount', 0)),
                    'published_at': datetime.fromisoformat(
                        video['snippet']['publishedAt'].replace('Z', '+00:00')
                    ),
                    'channel_id': video['snippet']['channelId'],
                }
                videos.append(video_data)
            
            return videos
        except HttpError as e:
            logger.error(f"Error fetching videos from channel {channel_id}: {e}")
            return []
    
    def _parse_duration(self, iso_duration):
        """Convert ISO 8601 duration to seconds."""
        # Simple parser for common formats like PT1H30M45S
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, iso_duration)
        
        if match:
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2) or 0)
            seconds = int(match.group(3) or 0)
            return hours * 3600 + minutes * 60 + seconds
        return 0
    
    def validate_channel_id(self, channel_id):
        """Check if a channel ID is valid and accessible."""
        channel_info = self.get_channel_info(channel_id)
        return channel_info is not None


class YouTubeSyncService:
    """
    Higher-level service for syncing YouTube videos into the social feed.
    Manages the YouTubeVideo and BusinessReel creation/updates.
    """
    
    def __init__(self, api_key=None):
        """Initialize sync service with YouTube API."""
        self.youtube_service = YouTubeService(api_key)
    
    def sync_channel_videos(self, youtube_channel):
        """
        Fetch and sync latest videos from a YouTube channel.
        Creates BusinessReel entries for each video.
        
        Args:
            youtube_channel (YouTubeChannel): The channel to sync
            
        Returns:
            dict: Sync result with success count and errors
        """
        from .models import YouTubeVideo, BusinessReel
        
        result = {'synced': 0, 'skipped': 0, 'errors': []}
        
        try:
            # Determine sync window
            if youtube_channel.last_synced_at:
                published_after = youtube_channel.last_synced_at
            else:
                # First sync: limit to a safe historical window to conserve API quota
                safe_days = getattr(settings, 'YOUTUBE_INITIAL_SYNC_DAYS', 90)
                published_after = timezone.now() - timedelta(days=safe_days)
                logger.info(f"Initial sync for channel {youtube_channel.channel_id}: using last {safe_days} days window")
            
            # Fetch videos from YouTube
            videos = self.youtube_service.get_latest_videos(
                youtube_channel.channel_id,
                max_results=50,
                published_after=published_after
            )
            
            for video_data in videos:
                try:
                    # Check if video already exists
                    youtube_video, created = YouTubeVideo.objects.get_or_create(
                        youtube_id=video_data['youtube_id'],
                        defaults={
                            'channel': youtube_channel,
                            'title': video_data['title'],
                            'description': video_data['description'],
                            'thumbnail_url': video_data['thumbnail_url'],
                            'youtube_url': video_data['youtube_url'],
                            'duration_seconds': video_data['duration_seconds'],
                            'youtube_views': video_data['youtube_views'],
                            'youtube_likes': video_data['youtube_likes'],
                            'published_at': video_data['published_at'],
                        }
                    )
                    
                    if created and not youtube_video.business_reel:
                        # Create BusinessReel for this YouTube video using external URL fields
                        business_reel = BusinessReel.objects.create(
                            author=youtube_channel.partnership.user,
                            caption=video_data['title'] + '\n\n' + video_data['description'][:300],
                            external_video_url=video_data['youtube_url'],
                            external_thumbnail_url=video_data['thumbnail_url'],
                            language='en',
                            tags=f"youtube,{youtube_channel.channel_name}",
                            is_active=True,
                        )
                        youtube_video.business_reel = business_reel
                        youtube_video.save()
                        result['synced'] += 1
                    else:
                        result['skipped'] += 1
                
                except Exception as e:
                    error_msg = f"Error syncing video {video_data.get('youtube_id')}: {str(e)}"
                    logger.error(error_msg)
                    result['errors'].append(error_msg)
            
            # Update last synced timestamp
            youtube_channel.last_synced_at = timezone.now()
            youtube_channel.total_videos_synced += result['synced']
            youtube_channel.save()
            
        except Exception as e:
            error_msg = f"Error syncing channel {youtube_channel.channel_id}: {str(e)}"
            logger.error(error_msg)
            result['errors'].append(error_msg)
        
        return result
    
    def sync_all_active_channels(self):
        """
        Sync all active YouTube channels for approved partnerships.
        Call this from a periodic task (Celery or APScheduler).
        
        Returns:
            dict: Overall sync statistics
        """
        from .models import YouTubeChannel
        
        stats = {'total_synced': 0, 'channels_processed': 0, 'errors': []}
        
        active_channels = YouTubeChannel.objects.filter(
            is_syncing=True,
            partnership__is_active=True
        )
        
        for channel in active_channels:
            # Check if it's time to sync based on frequency
            if channel.last_synced_at:
                next_sync = channel.last_synced_at + timedelta(hours=channel.sync_frequency_hours)
                if timezone.now() < next_sync:
                    continue
            
            result = self.sync_channel_videos(channel)
            stats['total_synced'] += result['synced']
            stats['channels_processed'] += 1
            stats['errors'].extend(result['errors'])
        
        return stats

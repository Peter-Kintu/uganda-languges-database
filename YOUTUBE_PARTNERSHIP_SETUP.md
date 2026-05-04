# YouTube Partnership Integration - Setup Guide

## Overview

Your Africana AI social app now has a **YouTube Partnership** system that allows approved users to automatically sync content from YouTube channels into the social feed, while maintaining the sleek design and functionality of the platform.

## Key Features

### 1. **Partnership Applications**
- Users apply for YouTube partnership access
- Admin reviews and approves applications
- Approved partners get access to channel management dashboard

### 2. **Channel Management**
- Add multiple YouTube channels to sync from
- Control sync frequency (1-168 hours)
- View sync statistics and video count

### 3. **Automatic Video Syncing**
- Videos are automatically pulled from linked channels
- Synced videos appear as `BusinessReel` entries in the social feed
- Maintains all engagement features: likes, shares, downloads
- YouTube videos display with proper attribution

### 4. **Design Integration**
- YouTube videos embed seamlessly in the feed
- Smooth iframe player for YouTube content
- Fallback to native video player for uploaded content
- Consistent styling across all reel types

## Installation & Setup

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

Key packages added:
- `google-api-python-client` - YouTube Data API v3 client

### Step 2: Set Environment Variables

Add to your `.env` file:

```env
YOUTUBE_API_KEY=AIzaSyA5EUWnwUtpnrKUf9mGBrFOYNWq1Uw4aXQ
```

### Step 3: Run Migrations

```bash
python manage.py makemigrations social
python manage.py migrate social
```

This creates three new database tables:
- `YouTubePartnership` - Partnership applications and status
- `YouTubeChannel` - Linked YouTube channels
- `YouTubeVideo` - Cached video metadata

### Step 4: Configure Admin

YouTube partnership management is available in Django Admin:

```
http://your-domain/admin/social/
```

**Admin Actions:**
- Approve/Reject/Suspend partnerships
- Force sync channels manually
- Enable/disable channel syncing
- View synced videos and stats

## User Flow

### For Content Creators (Partners):

1. **Apply for Partnership**
   - Navigate to `/social/youtube/apply/`
   - Submit partnership application with reason
   - Wait for admin approval

2. **Add YouTube Channels**
   - Once approved, go to `/social/youtube/dashboard/`
   - Click "Add Channel"
   - Enter YouTube Channel ID (format: `UCxxxxxx`)
   - Set sync frequency (default: 24 hours)

3. **Monitor Sync**
   - Dashboard shows active channels
   - See video count, last sync time
   - Manual sync available via "Sync now" button

### For Admins:

1. **Review Applications**
   - Go to Admin Panel → YouTube Partnerships
   - Review partnership descriptions
   - Approve or reject applications

2. **Monitor Quota**
   - Each partnership tracks API quota (10,000 units/day)
   - Automatic tracking prevents exceeding limits

3. **Manual Sync**
   - Force sync individual channels from admin
   - Or use management command (see below)

## Management Commands

### Sync All Active Channels

```bash
python manage.py sync_youtube_videos
```

### Sync Specific Channel

```bash
python manage.py sync_youtube_videos --channel-id <CHANNEL_ID>
```

### Sync Partner's Channels

```bash
python manage.py sync_youtube_videos --partner-id <USER_ID>
```

### Force Sync (Ignore Frequency)

```bash
python manage.py sync_youtube_videos --force
```

## Automated Scheduling

To run syncs automatically, use **Celery** or **APScheduler**.

### With Celery Beat (Recommended):

```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'sync-youtube-videos': {
        'task': 'social.tasks.sync_youtube_videos_task',
        'schedule': crontab(minute=0, hour='*/6'),  # Every 6 hours
    },
}
```

```python
# social/tasks.py
from celery import shared_task
from .youtube_service import YouTubeSyncService

@shared_task
def sync_youtube_videos_task():
    service = YouTubeSyncService()
    return service.sync_all_active_channels()
```

## Video Display

### In the Social Feed:

YouTube videos appear as regular reels with:
- ✅ Full engagement: likes, shares, downloads
- ✅ Creator attribution with trust score
- ✅ YouTube embed player (autoplay, muted, controls hidden)
- ✅ Proper fallback for network issues

### Video Sources:

- **User Uploads**: Stored via CloudinaryField → `.video` field
- **YouTube Synced**: Stored as URL → `.external_video_url` field

The feed automatically detects the source and displays appropriately.

## API Quota Tracking

YouTube Data API has a daily limit of **10,000 quota units**.

### Costs:
- Search videos: 100 units
- Get channel info: 1 unit
- Get video details: 1 unit

### Tracking:
- Tracked per partnership in `daily_quota_used`
- Resets automatically at midnight UTC
- Shows in admin panel and dashboard

## Models Overview

### YouTubePartnership
```python
- user: OneToOne(User)
- status: pending, approved, rejected, suspended
- is_active: Boolean (controls sync ability)
- partnership_description: Text (reason for partnership)
- daily_quota_used: Integer (API quota tracking)
```

### YouTubeChannel
```python
- partnership: ForeignKey(YouTubePartnership)
- channel_id: String (YouTube Channel ID)
- channel_name: String
- is_syncing: Boolean
- sync_frequency_hours: Integer (1-168)
- last_synced_at: DateTime
- total_videos_synced: Integer
```

### YouTubeVideo
```python
- youtube_id: String (unique)
- channel: ForeignKey(YouTubeChannel)
- title, description, thumbnail_url
- youtube_url: YouTube watch link
- business_reel: ForeignKey(BusinessReel) - linked reel
- published_at, synced_at
```

## Testing

### Test Partnership Creation:

```python
from social.models import YouTubePartnership
from users.models import CustomUser

user = CustomUser.objects.create_user(username='test_partner', password='pass')
partnership = YouTubePartnership.objects.create(
    user=user,
    partnership_description="I want to share my tech channel",
    status='approved',
    is_active=True
)
```

### Test Channel Addition:

```python
from social.models import YouTubeChannel

channel = YouTubeChannel.objects.create(
    partnership=partnership,
    channel_id='UCxxxxxx',  # Your YouTube Channel ID
    channel_name='My Channel',
    sync_frequency_hours=24
)

# Manually sync
from social.youtube_service import YouTubeSyncService
service = YouTubeSyncService()
result = service.sync_channel_videos(channel)
print(result)  # {'synced': 5, 'skipped': 2, 'errors': []}
```

## Troubleshooting

### "Invalid Channel ID"
- Ensure format is `UCxxxxxx` (24 chars, starts with UC)
- Get from channel's About page, not from @username

### "API Key Error"
- Check `.env` file has `YOUTUBE_API_KEY`
- Verify key is enabled for YouTube Data API v3
- Ensure key restriction allows your domain

### "Quota Exceeded"
- Wait until next day (midnight UTC)
- Or request higher quota from Google Cloud

### Videos Not Appearing
- Check if partnership status is "approved"
- Run sync manually: `python manage.py sync_youtube_videos --channel-id <ID>`
- Check logs for errors

## Security Notes

⚠️ **API Key Security:**
- Never commit `.env` to git
- Use environment variables in production
- Restrict API key to your domain
- Limit to YouTube Data API v3 only

⚠️ **Partnership Control:**
- Admin approval required before syncing
- Quota tracking prevents abuse
- Can suspend partnerships anytime

## Next Steps

1. ✅ Set YouTube API key in `.env`
2. ✅ Run migrations
3. ✅ Test partnership application flow
4. ✅ Add first YouTube channel
5. ✅ Set up automated sync with Celery/APScheduler
6. ✅ Monitor API quota in admin

## Support

For API documentation, visit:
- [YouTube Data API v3 Docs](https://developers.google.com/youtube/v3)
- [Django Documentation](https://docs.djangoproject.com/)
- Your project README for general setup

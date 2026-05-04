# YouTube Integration - Quick Start (5 Min Setup)

## 1️⃣ Add API Key to .env

```bash
echo 'YOUTUBE_API_KEY=AIzaSyA5EUWnwUtpnrKUf9mGBrFOYNWq1Uw4aXQ' >> .env
```

## 2️⃣ Install Dependencies

```bash
pip install google-api-python-client
```

(Or just run `pip install -r requirements.txt`)

## 3️⃣ Run Migrations

```bash
python manage.py makemigrations social
python manage.py migrate
```

## 4️⃣ Test Everything Works

```bash
python manage.py runserver
```

Then visit:
- http://localhost:8000/admin/ → YouTube Partnerships section
- http://localhost:8000/social/youtube/apply/ → Apply for partnership

## 5️⃣ Approve a Partnership (Admin)

1. Go to Django Admin
2. YouTube Partnerships → Select a pending partnership
3. Click "Approve selected partnerships"
4. Refresh and user can now add channels

## 6️⃣ Add a YouTube Channel (As Approved Partner)

1. Go to http://localhost:8000/social/youtube/dashboard/
2. Click "Add Channel"
3. Enter Channel ID (get from youtube.com/channel/**UCxxxxx**)
4. Set sync frequency (24 hours = default)
5. Click "Add Channel"

## 7️⃣ Manual Sync

```bash
# Sync all channels
python manage.py sync_youtube_videos

# Sync specific channel
python manage.py sync_youtube_videos --channel-id 1

# Force sync now
python manage.py sync_youtube_videos --force
```

## 8️⃣ Set Up Auto Sync (Optional)

### With APScheduler:

```python
# Install: pip install APScheduler

# In manage.py or wsgi.py
from apscheduler.schedulers.background import BackgroundScheduler
from social.youtube_service import YouTubeSyncService

def sync_job():
    service = YouTubeSyncService()
    service.sync_all_active_channels()

scheduler = BackgroundScheduler()
scheduler.add_job(sync_job, 'interval', hours=6)
scheduler.start()
```

### With Celery (Production):

```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'sync-youtube': {
        'task': 'social.tasks.sync_videos',
        'schedule': crontab(minute=0, hour='*/6'),
    },
}

# social/tasks.py
@shared_task
def sync_videos():
    from social.youtube_service import YouTubeSyncService
    service = YouTubeSyncService()
    return service.sync_all_active_channels()
```

## 📊 Admin Dashboard Features

In Django Admin → YouTube Partnerships:
- ✅ See all partnership applications
- ✅ Approve/Reject/Suspend partnerships
- ✅ Monitor API quota usage
- ✅ View all linked channels
- ✅ Force sync individual channels
- ✅ Enable/Disable channel syncing

## 🎬 What Happens When Video Syncs

1. YouTube API fetches latest videos from channel
2. Creates `YouTubeVideo` record in database
3. Automatically creates `BusinessReel` entry
4. Video appears in social feed with:
   - YouTube embed player (iframe)
   - Creator attribution
   - Like/Share/Download buttons
   - Trust score display
   - Full engagement tracking

## 🔒 Security

- API Key restricted to your domain in Google Cloud Console
- Partnership approval required before syncing
- Daily quota limits prevent abuse
- Can suspend partnerships anytime

## 🚨 Troubleshooting

**Problem: "API Key not found"**
→ Check `.env` file exists and has `YOUTUBE_API_KEY=...`

**Problem: "Channel not found"**
→ Use format `UCxxxxxx` (from youtube.com/channel/UC...)

**Problem: "Videos not syncing"**
→ Check partnership status is "approved" in admin

**Problem: "API Quota Exceeded"**
→ Wait until next day (midnight UTC) or increase quota in Google Cloud

## 📚 Full Documentation

See `YOUTUBE_PARTNERSHIP_SETUP.md` for complete documentation.

## ✨ That's It!

Your app now syncs YouTube content while maintaining the beautiful Africana AI design.

Users apply → Admin approves → Partner adds channels → Videos auto-sync to feed!

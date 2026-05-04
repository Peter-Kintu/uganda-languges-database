# YouTube Partnership Architecture

## System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                      AFRICANA AI SOCIAL                          │
│                      (Social Feed - TikTok 2.0)                  │
└─────────────────────────────────────────────────────────────────┘

┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│   YouTube    │         │   YouTube    │         │   YouTube    │
│  Channel A   │         │  Channel B   │         │  Channel C   │
└──────┬───────┘         └──────┬───────┘         └──────┬───────┘
       │                        │                        │
       └────────────────────────┼────────────────────────┘
                                │
                    ┌───────────┴───────────┐
                    │  YouTube Data API v3  │
                    │  (OAuth Credentials)  │
                    └───────────┬───────────┘
                                │
         ┌──────────────────────┴──────────────────────┐
         │                                             │
    ┌────▼─────────────────────┐      ┌──────────────▼──────┐
    │  YouTubeSyncService      │      │  YouTubeService     │
    │  (Business Logic)        │      │  (API Wrapper)      │
    │  - Sync channels         │      │  - Fetch videos     │
    │  - Create BusinessReels  │      │  - Get metadata     │
    │  - Track quota           │      │  - Channel info     │
    └────┬─────────────────────┘      └──────────────┬──────┘
         │                                           │
    ┌────▼──────────────────────────────────────────┬────────┐
    │                                               │        │
    │        DJANGO DATABASE MODELS                 │        │
    │  ┌────────────────────────────────────┐       │        │
    │  │ YouTubePartnership                 │       │        │
    │  ├──────────────────────────────────┤       │        │
    │  │ - user (FK User)                 │       │        │
    │  │ - status (pending/approved...)   │       │        │
    │  │ - is_active                      │       │        │
    │  │ - daily_quota_used               │       │        │
    │  │ - partnership_description        │       │        │
    │  └────────────────────────────────────┘       │        │
    │                                               │        │
    │  ┌────────────────────────────────────┐       │        │
    │  │ YouTubeChannel                     │       │        │
    │  ├──────────────────────────────────┤       │        │
    │  │ - partnership (FK)                │       │        │
    │  │ - channel_id (YouTube ID)         │       │        │
    │  │ - is_syncing (Boolean)            │       │        │
    │  │ - sync_frequency_hours            │       │        │
    │  │ - last_synced_at                  │       │        │
    │  │ - total_videos_synced             │       │        │
    │  └────────────────────────────────────┘       │        │
    │                                               │        │
    │  ┌────────────────────────────────────┐       │        │
    │  │ YouTubeVideo                       │       │        │
    │  ├──────────────────────────────────┤       │        │
    │  │ - youtube_id (Unique)             │       │        │
    │  │ - channel (FK YouTubeChannel)     │       │        │
    │  │ - title, description              │       │        │
    │  │ - thumbnail_url                   │       │        │
    │  │ - youtube_url                     │       │        │
    │  │ - business_reel (FK) ─────────────┼───────┘        │
    │  │ - youtube_views, likes            │                │
    │  └────────────────────────────────────┘                │
    │                                                         │
    │  ┌────────────────────────────────────┐                │
    │  │ BusinessReel (EXTENDED)            │                │
    │  ├──────────────────────────────────┤                │
    │  │ - video (CloudinaryField)         │                │
    │  │ - external_video_url (NEW!)       │────────────┐   │
    │  │ - thumbnail                       │            │   │
    │  │ - external_thumbnail_url (NEW!)   │────────┐   │   │
    │  │ - caption                         │        │   │   │
    │  │ - author, likes, shares, etc.     │        │   │   │
    │  │ - is_external_video (property)    │        │   │   │
    │  │ - video_embed_url (property)      │        │   │   │
    │  └────────────────────────────────────┘        │   │   │
    │                                                 │   │   │
    └─────────────────────────────────────────────────┼───┼───┘
                                                      │   │
         ┌────────────────────────────────────────────┘   │
         │                                                │
    ┌────▼─────────────────────────────────────────┬──────▼──┐
    │          SOCIAL FEED (feed.html)             │         │
    │  ┌───────────────────────────────────────┐   │         │
    │  │ Video/Iframe Detection & Rendering    │   │         │
    │  │ - If external_video_url (YouTube)     │───┼──┐      │
    │  │   → Render as <iframe> (embed)        │   │  │      │
    │  │ - If video (Cloudinary)               │───┼──┼──┐   │
    │  │   → Render as <video> (native)        │   │  │  │   │
    │  └───────────────────────────────────────┘   │  │  │   │
    │                                              │  │  │   │
    │  ┌───────────────────────────────────────┐   │  │  │   │
    │  │ FULL ENGAGEMENT FOR ALL VIDEOS        │   │  │  │   │
    │  │ ❤️ Likes                               │   │  │  │   │
    │  │ 🔗 Share                               │   │  │  │   │
    │  │ 📥 Download                            │   │  │  │   │
    │  │ 💬 Comments (messages)                 │   │  │  │   │
    │  │ 🤝 Negotiate Price (if priced)        │   │  │  │   │
    │  │ 💼 Hire Me (if professional)          │   │  │  │   │
    │  └───────────────────────────────────────┘   │  │  │   │
    │                                              │  │  │   │
    │  ✨ TRUST SCORE & VERIFICATION              │  │  │   │
    │  - Updated on each like                     │  │  │   │
    │  - Verified merchant badges                │  │  │   │
    │  - Cryptographic seals                     │  │  │   │
    │                                              │  │  │   │
    └──────────────────────────────────────────────┼──┼──┼───┘
                                                   │  │  │
                                      ┌────────────┘  │  │
                                      │               │  │
                          ┌───────────┴───────────┐   │  │
                          │ YOUTUBE EMBED PLAYER  │   │  │
                          │ (If YouTube video)    │   │  │
                          │ - Autoplay=1          │───┘  │
                          │ - Mute=1              │      │
                          │ - Controls=0          │      │
                          │ - Fullscreen support  │      │
                          └───────────────────────┘      │
                                                         │
                             ┌───────────────────────────┴──────┐
                             │ NATIVE VIDEO PLAYER               │
                             │ (If uploaded/external)            │
                             │ - HTML5 <video>                   │
                             │ - Cloudinary optimization         │
                             │ - Low-bandwidth support           │
                             └───────────────────────────────────┘
```

## Sync Workflow

```
PARTNERSHIP APPLICATION FLOW
════════════════════════════

1. User visits /social/youtube/apply/
   ↓
2. Submits application with reason
   ↓
3. Status: "pending" (waiting for admin)
   ↓
4. Admin reviews in /admin/
   ↓
5. Admin approves partnership
   ├→ Status: "approved"
   ├→ is_active: True
   └→ approved_at: timestamp
   ↓
6. User visits /social/youtube/dashboard/
   ↓
7. Clicks "Add Channel"
   ↓
8. Enters YouTube Channel ID (UCxxxxxx)
   ↓
9. System validates with YouTube API
   ↓
10. Creates YouTubeChannel record
    ├→ channel_name fetched from API
    ├→ channel_thumbnail fetched
    └→ is_syncing: True by default
    ↓
11. AUTOMATIC INITIAL SYNC
    ├→ Fetches last 7 days of videos
    ├→ Creates YouTubeVideo records
    ├→ Creates BusinessReel for each
    └→ Videos appear in feed immediately
    ↓
12. SCHEDULED SYNCS (every N hours)
    ├→ Runs via management command
    ├→ Only fetches new videos
    ├→ Creates new BusinessReels
    └→ Users see updates in feed


API QUOTA FLOW
═════════════

Daily Limit: 10,000 units/day per project

Each Sync Operation:
  - Search for videos: 100 units
  - Get channel info: 1 unit
  - Get video stats: 1 unit per video
  ────────────────────────────────────
  Total per channel: ~102 units (for 50 videos)

Tracking:
  - Stored in YouTubePartnership.daily_quota_used
  - Resets automatically at midnight UTC
  - Prevents syncs if quota exceeded


MANAGEMENT COMMAND FLOW
══════════════════════

python manage.py sync_youtube_videos

├─ No args: Sync all active channels
│  └─ Respects sync_frequency_hours
│
├─ --channel-id 5: Sync specific channel
│  └─ Force sync regardless of frequency
│
├─ --partner-id 3: Sync all partner's channels
│  └─ Useful for testing
│
└─ --force: Ignore frequency limits
   └─ Immediate sync for all channels


ADMIN DASHBOARD FLOW
════════════════════

YouTube Partnerships (Admin Panel)
├─ List View
│  ├─ Filter by status
│  ├─ Filter by is_active
│  └─ Search by username/email
│
├─ Actions
│  ├─ Approve selected partnerships
│  ├─ Reject selected partnerships
│  └─ Suspend selected partnerships
│
├─ Inline Editing (YouTubeChannels)
│  ├─ Add/remove channels
│  ├─ Change sync frequency
│  └─ Toggle is_syncing
│
└─ Read-only Fields
   ├─ daily_quota_used (tracks API usage)
   ├─ last_quota_reset
   ├─ total_videos_synced
   └─ last_synced_at (per channel)
```

## Data Flow: From YouTube → Feed

```
YouTube API
    ↓
youtube_service.get_latest_videos(channel_id)
    ├─ Makes API calls
    ├─ Fetches video metadata
    ├─ Returns: [
    │     {
    │       'youtube_id': 'dQw...',
    │       'title': 'Video Title',
    │       'description': '...',
    │       'thumbnail_url': 'https://...',
    │       'youtube_url': 'https://youtube.com/watch?v=...',
    │       'published_at': datetime,
    │       'youtube_views': 1000,
    │       'youtube_likes': 50,
    │     },
    │     ...
    │  ]
    └─ Tracks quota usage
    ↓
YouTubeSyncService.sync_channel_videos(channel)
    ├─ Creates YouTubeVideo records
    │   └─ youtube_id, title, description, etc.
    │
    ├─ Creates BusinessReel for each
    │   ├─ author = channel.partnership.user
    │   ├─ caption = title + description
    │   ├─ external_video_url = youtube URL
    │   ├─ external_thumbnail_url = thumbnail
    │   ├─ tags = "youtube,channelname"
    │   └─ is_active = True
    │
    └─ Links: YouTubeVideo.business_reel → BusinessReel
    ↓
Social Feed (/social/feed/)
    ├─ Query: BusinessReel.objects.filter(is_active=True)
    │
    ├─ For each reel:
    │   ├─ If reel.is_external_video:
    │   │   └─ Render <iframe> with reel.video_embed_url
    │   └─ Else:
    │       └─ Render <video> with reel.source_video_url
    │
    └─ Full engagement available:
        ├─ Like button
        ├─ Share button  
        ├─ Download button
        ├─ Creator profile with trust score
        └─ Message/Hire button
```

## Security Flow

```
API Key Management
══════════════════

Production:
  .env file (Git-ignored)
  ↓
  os.getenv('YOUTUBE_API_KEY')
  ↓
  Google Cloud Console
  ├─ Restrict to https://africanaai.info/
  ├─ Limit to YouTube Data API v3 only
  └─ Monitor usage

Development:
  .env.local (Git-ignored)
  ↓
  Test API key (restricted)
  ↓
  Local testing only


Partnership Control Flow
════════════════════════

Unapproved User
  └─ Cannot sync videos
     └─ Views: 403 Forbidden
     └─ Forms: Disabled
     └─ Admin: No channels visible

Approved User  
  ├─ Can view dashboard
  ├─ Can add channels
  ├─ Videos sync automatically
  └─ Engagement tracked

Suspended User
  ├─ Cannot add channels
  ├─ Existing channels stop syncing
  └─ Quota tracking frozen
  
Admin/Superuser
  └─ Full management access
```

## Performance Optimization

```
Query Optimization
═══════════════════

Feed View:
  BusinessReel.objects
    .filter(is_active=True)
    .select_related('author', 'author__social_profile')
    .order_by('-created_at')
  
  └─ Eliminates N+1 queries
  └─ Pre-fetches related data
  └─ Efficient for 1000+ reels


Caching Strategy
════════════════

YouTubeVideo metadata cached in DB:
  └─ Reduces API calls
  └─ Faster feed rendering
  └─ Falls back to YouTube if URL fails

Cloudinary Image Transforms:
  └─ Thumbnails cached
  └─ Automatic optimization
  └─ CDN delivery


Quota Management
═════════════════

Daily Limit: 10,000 units
Typical usage per partner:
  └─ 1 channel, 50 videos = 102 units
  └─ 100 channels possible per day

Prevention:
  └─ Track in database
  └─ Prevent sync if exceeded
  └─ Reset at midnight UTC
```

---

**Key Insight:** YouTube videos are stored as **external URLs** in `BusinessReel`, creating a bridge between YouTube content and the Africana social feed without duplicating video files. All engagement features (likes, shares, trust scores) work identically for both uploaded and synced content.

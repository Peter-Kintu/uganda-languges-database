from django.urls import path
from django.views.generic.base import RedirectView
from . import views

# The namespace used in {% url 'social:...' %}
app_name = 'social'

urlpatterns = [
    # Redirect /social/ to the actual feed path for legacy compatibility
    path('', RedirectView.as_view(pattern_name='social:social_feed', permanent=False), name='social_root_redirect'),

    # --- PILLAR 2: DISCOVERY LAYER ---
    # Main social feed displaying Business Reels (TikTok 2.0 Shoppable Feed)
    path('feed/', views.FeedView.as_view(), name='social_feed'),
    
    # Africa-First Upload Flow: Optimized for low-latency video publishing
    # UPDATED: Now also captures/updates WhatsApp contact info via the upload form
    path('publish/', views.upload_reel, name='upload_reel'),

    # --- SOCIAL INTERACTION PROTOCOLS ---
    # Endpoint for the Heart/Like button
    path('reel/<int:reel_id>/like/', views.toggle_like_reel, name='toggle_like'),
    
    # Analytics for Share & Download (Africana AI Branding)
    path('reel/<int:reel_id>/track-share/', views.track_share, name='track_share'),
    path('reel/<int:reel_id>/track-download/', views.track_download, name='track_download'),
    
    # --- PILLAR 3: AGENTIC COMMERCE & NEGOTIATION ---
    # The 'Haggle' Protocol: Real-time AI price negotiation endpoint
    path('negotiate/<int:reel_id>/', views.ai_negotiate_price, name='ai_negotiate'),
    
    # --- PILLAR 4: SOVEREIGN MESSAGING (WHATSAPP STYLE) ---
    # View all ongoing conversations (The Inbox)
    path('messages/', views.inbox, name='inbox'),
    
    # The Chat Thread between sender and receiver (The specific conversation)
    path('chat/<int:partner_id>/', views.chat_detail, name='chat_detail'),

    # The 'Hire' Protocol: Gateway to initiate the secure handshake
    # UPDATED: Now returns a WhatsApp redirect URL if the creator has a linked number
    path('hire/<int:reel_id>/', views.initiate_hire_protocol, name='hire_protocol'),
    
    # --- PILLAR 4: TRUST & IDENTITY ---
    # Bento-style Profile: Modern 'Proof of Work' layout using username slugs
    path('profile/<str:username>/', views.BentoProfileView.as_view(), name='bento_profile'),
    
    # --- PILLAR 5: YOUTUBE PARTNERSHIP & CONTENT SYNDICATION ---
    # Partnership application
    path('youtube/apply/', views.apply_youtube_partnership, name='youtube_apply'),
    
    # Partnership dashboard
    path('youtube/dashboard/', views.youtube_partnership_dashboard, name='youtube_partnership_dashboard'),
    
    # Add YouTube channel
    path('youtube/add-channel/', views.add_youtube_channel, name='add_youtube_channel'),
    
    # Remove YouTube channel
    path('youtube/remove-channel/<int:channel_id>/', views.remove_youtube_channel, name='remove_youtube_channel'),
    
    # Manual sync trigger
    path('youtube/sync/<int:channel_id>/', views.sync_youtube_channel_now, name='sync_youtube_channel'),
]
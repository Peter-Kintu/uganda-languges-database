from django.urls import path
from . import views

# The namespace used in {% url 'social:...' %}
app_name = 'social'

urlpatterns = [
    # --- PILLAR 2: DISCOVERY LAYER ---
    # Main social feed displaying Business Reels (TikTok 2.0 Shoppable Feed)
    path('feed/', views.FeedView.as_view(), name='social_feed'),
    
    # Africa-First Upload Flow: Optimized for low-latency video publishing
    # Note: Ensure the "Deploy" button in upload.html is visible via the updated Z-index
    path('publish/', views.upload_reel, name='upload_reel'),

    # --- SOCIAL INTERACTION PROTOCOLS (NEW) ---
    # Endpoint for the Heart/Like button
    path('reel/<int:reel_id>/like/', views.toggle_like_reel, name='toggle_like'),
    
    # Analytics for Share & Download (Africana AI Branding)
    path('reel/<int:reel_id>/track-share/', views.track_share, name='track_share'),
    path('reel/<int:reel_id>/track-download/', views.track_download, name='track_download'),
    
    # --- PILLAR 3: AGENTIC COMMERCE & MESSAGING ---
    # The 'Haggle' Protocol: Real-time AI price negotiation endpoint
    path('negotiate/<int:reel_id>/', views.ai_negotiate_price, name='ai_negotiate'),
    
    # The 'Hire' Protocol: Initiate secure messaging/inquiries
    path('hire/<int:reel_id>/', views.initiate_hire_protocol, name='hire_protocol'),
    
    # --- PILLAR 4: TRUST & IDENTITY ---
    # Bento-style Profile: Modern 'Proof of Work' layout using username slugs
    # If using the 'users' app for the main profile, this remains for deep-linking 
    # to specific bento-configured views.
    path('profile/<str:username>/', views.BentoProfileView.as_view(), name='bento_profile'),
]
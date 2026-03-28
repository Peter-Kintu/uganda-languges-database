from django.urls import path
from . import views

# The namespace used in {% url 'social:...' %}
app_name = 'social'

urlpatterns = [
    # --- PILLAR 2: DISCOVERY LAYER ---
    # Main social feed displaying Business Reels (TikTok 2.0 Shoppable Feed)
    path('feed/', views.FeedView.as_view(), name='social_feed'),
    
    # --- PILLAR 3: AGENTIC COMMERCE & MESSAGING ---
    # The 'Haggle' Protocol: Real-time AI price negotiation endpoint
    path('negotiate/<int:reel_id>/', views.ai_negotiate_price, name='ai_negotiate'),
    
    # The 'Hire' Protocol: Initiate secure messaging/inquiries for a specific service/reel
    path('hire/<int:reel_id>/', views.initiate_hire_protocol, name='hire_protocol'),
    
    # Africa-First Upload Flow: Optimized for low-latency video publishing
    path('publish/', views.upload_reel, name='upload_reel'),
    
    # --- PILLAR 4: TRUST & IDENTITY ---
    # Bento-style Profile: Modern 'Proof of Work' layout using username slugs
    path('profile/<str:username>/', views.BentoProfileView.as_view(), name='bento_profile'),
]
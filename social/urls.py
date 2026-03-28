from django.urls import path
from . import views

# The namespace used in {% url 'social:...' %}
app_name = 'social'

urlpatterns = [
    # --- PILLAR 2: DISCOVERY LAYER ---
    # Main social feed displaying Business Reels (TikTok 2.0 style)
    path('feed/', views.FeedView.as_view(), name='social_feed'),
    
    # --- PILLAR 3: AGENTIC COMMERCE ---
    # The 'Haggle' Protocol: Path for AI price negotiation logic
    path('negotiate/<int:reel_id>/', views.ai_negotiate_price, name='ai_negotiate'),
    
    # Front-end upload flow for users to post reels and set AI floor prices
    path('publish/', views.upload_reel, name='upload_reel'),
    
    # --- PILLAR 4: TRUST & IDENTITY ---
    # Bento-style profile view using the username slug (LinkedIn 2.0 style)
    path('profile/<str:username>/', views.BentoProfileView.as_view(), name='bento_profile'),
]
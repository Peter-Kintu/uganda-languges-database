from django.urls import path
from languages.views import robots_txt
from .views import google_verification, tts_proxy
from users.views import gemini_proxy
from . import views

app_name = 'users'

urlpatterns = [
    # --- Infrastructure & SEO ---
    path('googlec0826a61eabee54e.html', google_verification),
    path("robots.txt", robots_txt),

    # --- Authentication ---
    path('login/', views.user_login, name='user_login'),
    path('register/', views.user_register, name='user_register'),
    path('logout/', views.user_logout, name='user_logout'),
    
    # --- Profile Management ---
    path('profile/', views.user_profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # --- AI Services & Career Tools ---
    # Consider versioning your AI API for future stability
    path("api/v1/gemini_proxy/", gemini_proxy, name="gemini_proxy"),
    path('profile/ai-companion/', views.profile_ai, name='profile_ai'), # Renamed for clarity
    path('api/v1/tts/', tts_proxy, name='tts_proxy'),
]
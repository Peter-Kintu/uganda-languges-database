from django.urls import path
from languages.views import robots_txt
from . import views

app_name = 'users'

urlpatterns = [
    # --- Infrastructure & SEO ---
    path('googlec0826a61eabee54e.html', views.google_verification),
    path("robots.txt", robots_txt),

    # --- Authentication ---
    path('', views.user_login, name='root_login'),
    path('login/', views.user_login, name='user_login'),

    path('google-auth-receiver/', views.google_auth_receiver, name='google_auth_receiver'),
    # Legacy callback route alias for any old Google callback configuration.
    path('callback/', views.user_login, name='google_callback_legacy'),

    path('register/', views.user_register, name='user_register'),
    path('logout/', views.user_logout, name='user_logout'),
    
    # --- Profile Management ---
    path('profile/', views.user_profile, name='profile'),
    path('profile/request-payout/', views.profile_payout_request, name='profile_payout_request'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # --- Language Settings ---
    path('update-language/', views.update_language, name='update_language'),

    # --- AI Services & Career Tools ---
    path("api/v1/cerebras_proxy/", views.cerebras_proxy, name="cerebras_proxy"),
    path("api/v1/generate_image/", views.generate_advert_image, name="generate_advert_image"), # <-- Sunbird image generation endpoint
    path("profile/ai-companion/export-pdf/", views.generate_document_pdf, name="generate_document_pdf"),
    path('profile/ai-companion/', views.profile_ai, name='profile_ai'),
    path('api/v1/tts/', views.tts_proxy, name='tts_proxy'),
]
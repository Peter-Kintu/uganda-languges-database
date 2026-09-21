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

    # --- Nylon Payments ---
    path('payments/nylon/start/', views.nylon_start_checkout, name='nylon_start_checkout'),
    path('payments/nylon/status/<int:payment_id>/', views.nylon_payment_status, name='nylon_payment_status'),
    path('api/payments/nylon/webhook/', views.nylon_webhook, name='nylon_webhook'),
    path('payments/nylon/callback/', views.nylon_callback, name='nylon_callback'),

    # Temporary aliases for old links. New pages use the Nylon routes above.
    path('payments/pesapal/start/', views.nylon_start_checkout, name='pesapal_start_checkout'),
    path('api/payments/pesapal/ipn/', views.legacy_pesapal_webhook, name='pesapal_ipn'),
    path('payments/pesapal/callback/', views.nylon_callback, name='pesapal_callback'),

    # --- Language Settings ---
    path('update-language/', views.update_language, name='update_language'),

    # --- AI Services & Career Tools ---
    path("api/v1/analyze_ai_attachment/", views.analyze_ai_attachment, name="analyze_ai_attachment"),
    path("api/v1/agent/", views.agent_command, name="agent_command"),
    path("api/v1/cerebras_proxy/", views.cerebras_proxy, name="cerebras_proxy"),
    path("api/v1/generate_image/", views.generate_advert_image, name="generate_advert_image"), # <-- Sunbird image generation endpoint
    path("profile/ai-companion/export-pdf/", views.generate_document_pdf, name="generate_document_pdf"),
    path('profile/ai-companion/', views.profile_ai, name='profile_ai'),
    path('api/v1/tts/', views.tts_proxy, name='tts_proxy'),
]
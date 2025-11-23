from django.urls import path
from .views import tts_proxy
from users.views import gemini_proxy
from . import views

app_name = 'users'

urlpatterns = [
    # AUTHENTICATION
    path('login/', views.user_login, name='user_login'),
    path('register/', views.user_register, name='user_register'),
    path('logout/', views.user_logout, name='user_logout'),
    
    # PROFILE
    path('profile/', views.user_profile, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),

    # ai
    path("api/gemini_proxy/", gemini_proxy, name="gemini_proxy"),
     # AI Quiz Generator URL - FIXED
    path('profile_ai/', views.ai_quiz_generator, name='profile_ai'),
    
 
   
    path('tts/', tts_proxy, name='tts_proxy'),
]
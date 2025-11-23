from django.urls import path
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
]
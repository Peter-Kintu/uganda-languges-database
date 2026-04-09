from django.urls import path
from . import views

app_name = 'hotel'

urlpatterns = [
    path('', views.social_feed, name='social_feed'),
    path('create_post/', views.create_post, name='create_post'),
    path('like_post/<int:post_id>/', views.like_post, name='like_post'),
    path('add_comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('translate/', views.translate_text, name='translate_text'),
    path('send_message/<int:user_id>/', views.send_message, name='send_message'),
    path('inbox/', views.inbox, name='inbox'),
    path('share_post/<int:post_id>/', views.share_post, name='share_post'),
    path('get_recent_messages/', views.get_recent_messages, name='get_recent_messages'),
]
from django.urls import path
from . import views

app_name = 'hotel'

urlpatterns = [
    path('', views.social_feed, name='social_feed'),
    path('create_post/', views.create_post, name='create_post'),
    path('post/', views.public_create_post, name='post'),
    path('like-post/<int:post_id>/', views.like_post, name='like_post'),
    path('add-comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('translate/', views.translate_text, name='translate_text'),
    path('send_message/<int:user_id>/', views.send_message, name='send_message'),
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/messages/', views.inbox_messages, name='inbox_messages'),
    path('inbox/communities/', views.inbox_communities, name='inbox_communities'),
    path('inbox/notifications/', views.inbox_notifications, name='inbox_notifications'),
    path('mark-message-read/<int:message_id>/', views.mark_message_read, name='mark_message_read'),
    path('conversation/<int:user_id>/', views.conversation, name='conversation'),
    path('create_community/', views.create_community, name='create_community'),
    path('community/join/<str:invite_link>/', views.join_community, name='join_community'),
    path('community/<int:community_id>/', views.community_conversation, name='community_conversation'),
    path('follow/<int:user_id>/', views.follow_user, name='follow_user'),
    path('unfollow/<int:user_id>/', views.unfollow_user, name='unfollow_user'),
    path('share-post/<int:post_id>/', views.share_post, name='share_post'),
    path('get_recent_messages/', views.get_recent_messages, name='get_recent_messages'),
    path('gemini-translate/', views.gemini_translate, name='gemini_translate'),
    path('send_connection_request/<int:user_id>/', views.send_connection_request, name='send_connection_request'),
]
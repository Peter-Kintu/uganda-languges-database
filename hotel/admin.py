from django.contrib import admin
from .models import Post, Comment, Like, Connection

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'content', 'created_at')
    list_filter = ('created_at', 'author')
    search_fields = ('content', 'author__username')

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('author', 'post', 'content', 'created_at')
    list_filter = ('created_at', 'author')
    search_fields = ('content', 'author__username', 'post__content')

@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('user__username', 'post__content')

@admin.register(Connection)
class ConnectionAdmin(admin.ModelAdmin):
    list_display = ('sender', 'receiver', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('sender__username', 'receiver__username')
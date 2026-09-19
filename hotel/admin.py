from django.contrib import admin
from .models import (
    Post, Comment, Like, Connection, Community, CommunityChannel,
    CommunityMembership, CommunityModerationRule, CommunityRole,
)

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ('author', 'content', 'location', 'created_at')
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


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'creator', 'created_at')
    search_fields = ('name', 'description', 'creator__username')


@admin.register(CommunityChannel)
class CommunityChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'community', 'is_announcement', 'created_by', 'created_at')
    list_filter = ('is_announcement', 'created_at')
    search_fields = ('name', 'community__name')


@admin.register(CommunityRole)
class CommunityRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'community', 'can_post', 'can_create_threads', 'can_pin', 'can_moderate')
    list_filter = ('can_post', 'can_create_threads', 'can_pin', 'can_moderate')
    search_fields = ('name', 'community__name')


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'community', 'role', 'directory_visible', 'mentions_only', 'joined_at')
    list_filter = ('directory_visible', 'mentions_only', 'joined_at')
    search_fields = ('user__username', 'community__name')


@admin.register(CommunityModerationRule)
class CommunityModerationRuleAdmin(admin.ModelAdmin):
    list_display = ('phrase', 'community', 'action', 'is_active')
    list_filter = ('action', 'is_active')
    search_fields = ('phrase', 'community__name')

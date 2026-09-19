import uuid
from django.db import models
from django.conf import settings

class Post(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    image = models.ImageField(upload_to='posts/', blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    impressions = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Post by {self.author.username}: {self.content[:50]}"


class FeedImpression(models.Model):
    CONTENT_TYPES = [('post', 'Post'), ('product', 'Product'), ('job', 'Job')]

    viewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, blank=True)
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPES)
    object_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['viewer', 'session_key', 'content_type', 'object_id'],
                name='unique_feed_impression_per_session',
            ),
        ]

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.author.username} on {self.post}"

class Like(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"Like by {self.user.username} on {self.post}"

class Connection(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_connections')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_connections')
    status = models.CharField(max_length=10, choices=[('pending', 'Pending'), ('accepted', 'Accepted')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"Connection from {self.sender.username} to {self.receiver.username}"

class Message(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hotel_sent_messages')
    receiver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='hotel_received_messages')
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message from {self.sender.username} to {self.receiver.username}"

    class Meta:
        ordering = ['created_at']

class Share(models.Model):
    original_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='shares')
    sharer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    caption = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sharer.username} shared {self.original_post}"

    class Meta:
        ordering = ['-created_at']

class Community(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_communities')
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='communities', blank=True)
    invite_link = models.CharField(max_length=100, unique=True, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Community: {self.name} by {self.creator.username}"

    def save(self, *args, **kwargs):
        if not self.invite_link:
            self.invite_link = str(uuid.uuid4())[:8]
        super().save(*args, **kwargs)


class CommunityRole(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='roles')
    name = models.CharField(max_length=60)
    can_post = models.BooleanField(default=True)
    can_create_threads = models.BooleanField(default=True)
    can_pin = models.BooleanField(default=False)
    can_moderate = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['community', 'name'], name='unique_community_role_name'),
        ]
        ordering = ['name']

    def __str__(self):
        return f'{self.community.name}: {self.name}'


class CommunityMembership(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='community_memberships')
    role = models.ForeignKey(CommunityRole, on_delete=models.SET_NULL, null=True, blank=True, related_name='memberships')
    directory_visible = models.BooleanField(default=True)
    mentions_only = models.BooleanField(default=False)
    muted_until = models.DateTimeField(null=True, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['community', 'user'], name='unique_community_membership'),
        ]


class CommunityChannel(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='channels')
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subchannels')
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=255, blank=True)
    slug = models.SlugField(max_length=90)
    is_announcement = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_community_channels')
    created_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['community', 'slug'], name='unique_community_channel_slug'),
        ]
        ordering = ['position', 'name']

    def __str__(self):
        return f'{self.community.name} / {self.name}'


class CommunityModerationRule(models.Model):
    ACTION_CHOICES = [('hold', 'Hold for review'), ('reject', 'Reject')]
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='moderation_rules')
    phrase = models.CharField(max_length=120)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='hold')
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['community', 'phrase'], name='unique_community_moderation_phrase'),
        ]


class CommunityMessage(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='messages')
    channel = models.ForeignKey(CommunityChannel, on_delete=models.SET_NULL, null=True, blank=True, related_name='messages')
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField(blank=True)
    attachment = models.FileField(upload_to='message_attachments/', blank=True, null=True)
    moderation_status = models.CharField(max_length=10, choices=[('visible', 'Visible'), ('held', 'Held'), ('rejected', 'Rejected')], default='visible')
    moderation_reason = models.CharField(max_length=255, blank=True)
    is_pinned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message in {self.community.name} by {self.sender.username}"

    class Meta:
        ordering = ['created_at']
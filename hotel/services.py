from django.db.models import Q

from .models import CommunityMembership, CommunityModerationRule, CommunityRole


def ensure_community_defaults(community, user):
    """Create the default channel, roles, and membership for a new community."""
    from .models import CommunityChannel

    admin_role, _ = CommunityRole.objects.get_or_create(
        community=community,
        name='Admin',
        defaults={'can_post': True, 'can_create_threads': True, 'can_pin': True, 'can_moderate': True},
    )
    CommunityRole.objects.get_or_create(community=community, name='Member')
    channel, _ = CommunityChannel.objects.get_or_create(
        community=community,
        slug='general',
        defaults={'name': 'General', 'description': 'The main community conversation.', 'created_by': user},
    )
    membership, _ = CommunityMembership.objects.get_or_create(
        community=community,
        user=user,
        defaults={'role': admin_role},
    )
    if membership.role_id != admin_role.id:
        membership.role = admin_role
        membership.save(update_fields=['role'])
    return channel


def get_membership(community, user):
    return CommunityMembership.objects.select_related('role').filter(community=community, user=user).first()


def can_post_to_community(community, user, channel=None):
    membership = get_membership(community, user)
    if not membership:
        return False, 'Join this community before posting.'
    if channel and channel.community_id != community.id:
        return False, 'That channel does not belong to this community.'
    if membership.role and not membership.role.can_post:
        return False, 'Your current role cannot post in this community.'
    if channel and channel.is_announcement and membership.role and not membership.role.can_moderate:
        return False, 'Only community moderators can post announcements.'
    return True, ''


def moderate_community_content(community, content):
    """Return a moderation decision before content is persisted visibly."""
    normalized = (content or '').casefold()
    rules = CommunityModerationRule.objects.filter(community=community, is_active=True)
    for rule in rules:
        if rule.phrase.casefold() in normalized:
            status = 'rejected' if rule.action == 'reject' else 'held'
            return status, f'Matched moderation rule: {rule.phrase}'
    link_count = normalized.count('http://') + normalized.count('https://') + normalized.count('www.')
    if link_count >= 3:
        return 'held', 'Multiple external links require moderator review.'
    return 'visible', ''


def visible_community_messages(community, channel=None):
    query = community.messages.filter(moderation_status='visible').select_related('sender', 'channel')
    if channel:
        query = query.filter(Q(channel=channel) | Q(channel__isnull=True))
    return query.order_by('created_at')

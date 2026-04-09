from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from .models import Post, Comment, Like, Connection, Message, Share
from .forms import PostForm
from users.models import CustomUser
from django.conf import settings
import requests

@login_required
def social_feed(request):
    # Get user's connections
    connected_users = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    ).values_list('sender', 'receiver')
    
    # Flatten the list and remove duplicates, excluding current user
    connected_user_ids = set()
    for sender, receiver in connected_users:
        if sender != request.user.id:
            connected_user_ids.add(sender)
        if receiver != request.user.id:
            connected_user_ids.add(receiver)
    
    # Include the current user
    connected_user_ids.add(request.user.id)
    
    # Get posts from user and connections
    posts = Post.objects.filter(author_id__in=connected_user_ids).order_by('-created_at')
    
    # Get shares from user and connections
    shares = Share.objects.filter(sharer_id__in=connected_user_ids).order_by('-created_at')
    
    # Combine posts and shares into a single feed
    feed_items = []
    
    for post in posts:
        feed_items.append({
            'type': 'post',
            'item': post,
            'created_at': post.created_at
        })
    
    for share in shares:
        feed_items.append({
            'type': 'share',
            'item': share,
            'created_at': share.created_at
        })
    
    # Sort by creation date
    feed_items.sort(key=lambda x: x['created_at'], reverse=True)
    
    connections = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    )
    all_users = CustomUser.objects.exclude(id=request.user.id)
    context = {
        'feed_items': feed_items,
        'connections': connections,
        'all_users': all_users,
    }
    return render(request, 'hotel/social_feed.html', context)

@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Post created successfully!')
            return redirect('hotel:social_feed')
    else:
        form = PostForm()
    return render(request, 'hotel/create_post.html', {'form': form})

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(post=post, user=request.user)
    if not created:
        like.delete()
    return JsonResponse({'likes_count': post.likes.count()})

@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content')
        if content:
            Comment.objects.create(post=post, author=request.user, content=content)
    return redirect('hotel:social_feed')

@login_required
def send_connection_request(request, user_id):
    receiver = get_object_or_404(settings.AUTH_USER_MODEL, id=user_id)
    if receiver != request.user:
        Connection.objects.get_or_create(sender=request.user, receiver=receiver)
        messages.success(request, f'Connection request sent to {receiver.username}!')
    return redirect('hotel:social_feed')

@login_required
def accept_connection(request, connection_id):
    connection = get_object_or_404(Connection, id=connection_id, receiver=request.user)
    connection.status = 'accepted'
    connection.save()
    messages.success(request, f'Connected with {connection.sender.username}!')
    return redirect('hotel:social_feed')

@login_required
def translate_text(request):
    text = request.GET.get('text', '')
    target_lang = request.user.language or 'en'
    translated = translate_via_api(text, target_lang)
    return JsonResponse({'translated': translated})

def translate_via_api(text, target_lang):
    """
    Simple translation function. For now, returns original text.
    In production, integrate with a proper translation service.
    """
    # TODO: Implement proper translation API
    # For now, just return the original text
    return text

@login_required
def send_message(request, user_id):
    receiver = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
        except:
            content = request.POST.get('content', '')
        
        if content:
            Message.objects.create(sender=request.user, receiver=receiver, content=content)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': f'Message sent to {receiver.username}!'})
            else:
                messages.success(request, f'Message sent to {receiver.username}!')
                return redirect('users:profile', username=receiver.username)
    return redirect('users:profile', username=receiver.username)

@login_required
def inbox(request):
    messages_list = Message.objects.filter(receiver=request.user).order_by('-created_at')
    return render(request, 'hotel/inbox.html', {'messages': messages_list})

@login_required
def share_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        caption = request.POST.get('caption', '')
        Share.objects.create(original_post=post, sharer=request.user, caption=caption)
        messages.success(request, 'Post shared successfully!')
        return redirect('hotel:social_feed')
    return render(request, 'hotel/share_post.html', {'post': post})

@login_required
def get_recent_messages(request):
    messages_list = Message.objects.filter(receiver=request.user).order_by('-created_at')[:5]
    messages_data = []
    for msg in messages_list:
        messages_data.append({
            'sender': msg.sender.username,
            'sender_id': msg.sender.id,
            'content': msg.content[:50],
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'is_read': msg.is_read
        })
    return JsonResponse({'messages': messages_data})
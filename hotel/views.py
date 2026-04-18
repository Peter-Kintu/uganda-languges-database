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
import json
from google import genai

@login_required
def social_feed(request):
    # Check if user wants to translate the entire feed
    translate_feed = request.GET.get('translate', 'false').lower() == 'true'
    target_lang = request.GET.get('lang', request.user.language or 'en')
    
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
    
    # Get posts from user and connections - OR show all posts for public feed
    posts = Post.objects.all().order_by('-created_at')[:50]  # Show recent posts from everyone
    
    # Get shares from user and connections
    shares = Share.objects.all().order_by('-created_at')[:20]
    
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
    
    # Translate feed items if requested
    if translate_feed and target_lang != 'en':
        for item in feed_items:
            if item['type'] == 'post':
                try:
                    translated_content = translate_via_gemini(item['item'].content, target_lang)
                    item['translated_content'] = translated_content
                except:
                    item['translated_content'] = item['item'].content
            elif item['type'] == 'share':
                try:
                    translated_caption = translate_via_gemini(item['item'].caption or '', target_lang)
                    item['translated_caption'] = translated_caption
                except:
                    item['translated_caption'] = item['item'].caption or ''
    
    connections = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    )
    all_users = CustomUser.objects.exclude(id=request.user.id)
    context = {
        'feed_items': feed_items,
        'connections': connections,
        'all_users': all_users,
        'translate_feed': translate_feed,
        'current_lang': target_lang,
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
        if not content:
            try:
                data = json.loads(request.body)
                content = data.get('content', '')
            except json.JSONDecodeError:
                content = ''
        if content:
            Comment.objects.create(post=post, author=request.user, content=content)
            return JsonResponse({'success': True})
    return JsonResponse({'success': False}, status=400)

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
    Simple translation function using Gemini API.
    """
    return translate_via_gemini(text, target_lang)

def translate_via_gemini(text, target_lang):
    """
    Translate text using Google Gemini API with support for African languages.
    """
    if not text or not text.strip():
        return text
    
    try:
        # Initialize Gemini client
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return text
        
        client = genai.Client(api_key=api_key)
        
        # Create translation prompt with African language support
        prompt = f"""Translate the following text to {target_lang}. 
This is a social media post, so maintain the casual, friendly tone.
Support for African languages: Swahili (sw), Luganda (lg), Zulu (zu), Xhosa (xh), Afrikaans (af), Amharic (am), Yoruba (yo), Hausa (ha), Arabic (ar), French (fr), Portuguese (pt), etc.

Return ONLY the translated text, nothing else:

{text}"""
        
        # Call Gemini API
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        translated_text = response.text.strip() if response.text else text
        return translated_text
        
    except Exception as e:
        print(f"Gemini translation error: {e}")
        return text

@login_required
def send_message(request, user_id):
    receiver = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            content = data.get('content', '')
        except json.JSONDecodeError:
            content = request.POST.get('content', '')
        
        if content:
            Message.objects.create(sender=request.user, receiver=receiver, content=content)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'success': True, 'message': f'Message sent to {receiver.username}!'} )
            else:
                messages.success(request, f'Message sent to {receiver.username}!')
                return redirect('hotel:inbox')
    return JsonResponse({'success': False}, status=400)

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
        # Return JSON for AJAX / fetch calls
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or 'application/json' in request.headers.get('Accept', '')
        )
        if is_ajax:
            return JsonResponse({'success': True, 'shares_count': post.shares.count()})
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

@login_required
def gemini_translate(request):
    """Translate text using Google Gemini API"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        target_language = data.get('target_language', 'en')
        
        if not text:
            return JsonResponse({'error': 'Text required'}, status=400)
        
        # Initialize Gemini client
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return JsonResponse({'error': 'API key not configured'}, status=500)
        
        client = genai.Client(api_key=api_key)
        
        # Create translation prompt
        prompt = f"""Translate the following text to {target_language}. 
Return ONLY the translated text, nothing else:

{text}"""
        
        # Call Gemini API
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt
        )
        
        translated_text = response.text.strip() if response.text else text
        
        return JsonResponse({
            'success': True,
            'translated': translated_text,
            'source_text': text,
            'target_language': target_language
        })
        
    except Exception as e:
        print(f"Gemini translation error: {e}")
        return JsonResponse({
            'error': str(e),
            'success': False
        }, status=500)
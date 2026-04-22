from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.core.cache import cache
from .models import Post, Comment, Like, Connection, Message, Share
from .forms import PostForm
from users.models import CustomUser
from django.conf import settings
import requests
import json
import os

@login_required
def social_feed(request):
    # 1. Get the Filter Type from URL parameters (e.g., ?type=images)
    feed_type = request.GET.get('type', 'all')
    
    # Translation parameters
    translate_feed = request.GET.get('translate', 'false').lower() == 'true'
    target_lang = request.GET.get('lang', getattr(request.user, 'language', 'en'))
    
    # 2. Get standard posts (from connections)
    connected_users = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    ).values_list('sender', 'receiver')
    
    connected_user_ids = {u for sub in connected_users for u in sub}
    connected_user_ids.add(request.user.id)
    
    # Base querysets
    regular_posts_query = Post.objects.filter(author_id__in=connected_user_ids).order_by('-created_at')
    partner_posts_query = Post.objects.filter(author__user_type='investor', author__is_approved=True).order_by('-created_at')

    # 3. Apply Filtering Logic to BOTH querysets
    if feed_type == 'text':
        # Posts with no images and no location
        filter_q = Q(image__isnull=True) & (Q(location__isnull=True) | Q(location=''))
        regular_posts_query = regular_posts_query.filter(filter_q)
        partner_posts_query = partner_posts_query.filter(filter_q)
        
    elif feed_type == 'images':
        # Posts that HAVE images
        regular_posts_query = regular_posts_query.exclude(image__isnull=True)
        partner_posts_query = partner_posts_query.exclude(image__isnull=True)
        
    elif feed_type == 'location':
        # Posts that HAVE location data
        regular_posts_query = regular_posts_query.exclude(location__isnull=True).exclude(location='')
        partner_posts_query = partner_posts_query.exclude(location__isnull=True).exclude(location='')

    # 4. Interleave Logic (Invisible to user)
    regular_posts = list(regular_posts_query)
    partner_posts = list(partner_posts_query)
    
    final_feed = []
    p_idx = 0  # Counter for partner posts
    
    for i, post in enumerate(regular_posts):
        final_feed.append(post)
        # Every 3 posts, inject 1 partner post if available
        if (i + 1) % 3 == 0 and p_idx < len(partner_posts):
            # Check to ensure we don't duplicate the same post if the partner 
            # is also a connection of the user
            if partner_posts[p_idx] not in final_feed:
                final_feed.append(partner_posts[p_idx])
            p_idx += 1

    # Translate posts if requested
    if translate_feed and target_lang != 'en':
        for post in final_feed:
            if post.content:  # Only translate if there's text
                post.translated_content = translate_smart(post.content, target_lang)
                post.is_translated = True

    connections = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    )
    all_users = CustomUser.objects.exclude(id=request.user.id)
    context = {
        'posts': final_feed,
        'connections': connections,
        'all_users': all_users,
        'current_filter': feed_type,
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

# ═════════════════════════════════════════════════════════════════════════════
# TRANSLATION CONFIGURATION - NLLB + LibreTranslate
# ═════════════════════════════════════════════════════════════════════════════

NLLB_URL = os.getenv("NLLB_API_URL")  # https://sing-sjf2.onrender.com/translate
LIBRE_URL = "https://libretranslate.com/translate"

# NLLB handles these African languages - LibreTranslate doesn't support well
NLLB_LANGS = {
    # Uganda
    'lg', 'nyn', 'ach', 'lgg', 'teo', 'xog', 'ttj', 'nyo', 'laj', 'alz',
    # East Africa
    'sw', 'zu', 'xh', 'yo', 'ha', 'am', 'luo', 'luy', 'kam', 'ki',
    # East/Southern Africa  
    'rw', 'rn', 'so', 'om', 'ti', 'st', 'nso', 'tn', 'ss', 've', 'nr',
    # West/Central/South Africa
    'ny', 'sn', 'tw', 'ak', 'ee', 'fon', 'ln', 'kg', 'mg'
}

def translate_smart(text, target_lang, source_lang='en'):
    """
    Intelligent translation routing:
    1. NLLB for African languages (Luganda, Swahili, Zulu, etc.)
    2. LibreTranslate for EU/Asian languages (French, Spanish, etc.)
    3. 7-day caching to save API calls
    4. Graceful fallbacks on errors
    """
    # Early returns for no-ops
    if not text or not text.strip() or target_lang == source_lang or target_lang == 'en':
        return text

    # Cache hit = instant return, saves API calls
    cache_key = f"trans_{hash(text)}_{source_lang}_{target_lang}"
    if cached := cache.get(cache_key):
        return cached

    translated = text

    # ═══════════════════════════════════════════════════════════════════════════
    # ROUTE 1: African languages → Your NLLB on Render
    # ═══════════════════════════════════════════════════════════════════════════
    if target_lang in NLLB_LANGS and NLLB_URL:
        try:
            r = requests.post(NLLB_URL, json={
                "text": text[:500],
                "target": target_lang,
                "source": source_lang
            }, timeout=12)
            if r.status_code == 200:
                translated = r.json().get('translated', text)
                cache.set(cache_key, translated, 604800)  # 7 days
                return translated
            else:
                print(f"NLLB error {r.status_code}: {r.text[:100]}")
        except Exception as e:
            print(f"NLLB failed: {e}, falling back to LibreTranslate")
            # Fall through to LibreTranslate for retry

    # ═══════════════════════════════════════════════════════════════════════════
    # ROUTE 2: Everything else → LibreTranslate (free, no key required)
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        res = requests.post(LIBRE_URL, json={
            "q": text[:500],
            "source": source_lang,
            "target": target_lang,
            "format": "text"
        }, timeout=4)
        if res.status_code == 200:
            translated = res.json().get('translatedText', text)
            cache.set(cache_key, translated, 604800)  # 7 days
            return translated
        else:
            print(f"LibreTranslate error {res.status_code}")
    except Exception as e:
        print(f"LibreTranslate failed: {e}")

    # Final fallback: return original text
    # Browser will offer Chrome/Safari automatic translation as backup
    print(f"Translation failed for {target_lang}, returning original")
    return text

@login_required
def translate_text(request):
    """API endpoint for translating text"""
    text = request.GET.get('text', '')
    target_lang = request.GET.get('target_lang', request.user.language or 'en')
    source_lang = request.GET.get('source_lang', 'en')
    
    if not text:
        return JsonResponse({'error': 'Text required'}, status=400)
    
    translated = translate_smart(text, target_lang, source_lang)
    return JsonResponse({'translated': translated})

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
            is_ajax = (
                request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
                'application/json' in request.headers.get('Content-Type', '')
            )
            if is_ajax:
                return JsonResponse({'success': True, 'message': f'Message sent to {receiver.username}!'})
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
    """Translate text using dual-service translation (NLLB + LibreTranslate)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        target_language = data.get('target_language', 'en')
        source_language = data.get('source_language', 'en')
        
        if not text:
            return JsonResponse({'error': 'Text required'}, status=400)
        
        # Check cache first
        cache_key = f"trans_{hash(text)}_{source_language}_{target_language}"
        if cached := cache.get(cache_key):
            return JsonResponse({
                'success': True,
                'translated': cached,
                'source_text': text,
                'target_language': target_language,
                'cached': True
            })
        
        # Use new smart translator
        translated = translate_smart(text, target_language, source_language)
        
        if translated == text and target_language != 'en':
            # Translation failed or returned original
            return JsonResponse({
                'success': False,
                'error': f'Translation to {target_language} failed. Browser translation available.',
                'fallback': 'browser',
                'original_text': text
            })
        
        return JsonResponse({
            'success': True,
            'translated': translated,
            'source_text': text,
            'target_language': target_language,
            'source_language': source_language,
            'cached': False
        })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Translation error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
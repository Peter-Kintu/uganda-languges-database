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
    Simple translation function using LibreTranslate.
    """
    return translate_via_gemini(text, target_lang)

LIBRE_URL = "https://libretranslate.com/translate"
LIBRE_API_KEY = os.environ.get("LIBRETRANSLATE_API_KEY", "")  # Optional: get from https://portal.libretranslate.com

def translate_via_gemini(text, target_lang):
    """
    Multi-service translation with fallbacks - completely free
    Supports: sw, zu, xh, af, am, yo, ha, ar, fr, pt, es, de, it, ru, zh, ja, ko, hi
    Falls back to browser translation for unsupported languages
    """
    if not text or not text.strip() or target_lang == 'en':
        return text

    # Cache 7 days - social posts don't change
    cache_key = f"translate_{hash(text)}_{target_lang}"
    if cached := cache.get(cache_key):
        return cached

    # Supported languages across all services - Expanded to include ALL African languages
    supported = {
        # East Africa
        'sw', 'lg', 'ki', 'luo', 'kam', 'dav', 'ebu', 'mer', 'so', 'am', 'om', 'ti', 'aa',
        # West Africa  
        'yo', 'ha', 'ig', 'bin', 'efi', 'ibb', 'tiv', 'nup', 'kr', 'ff', 'wo', 'mnk', 'bm', 'son', 'tw', 'ee', 'gaa', 'dag', 'mos',
        # Central Africa
        'ln', 'kg', 'lua', 'sg',
        # Southern Africa
        'zu', 'xh', 'af', 'st', 'tn', 'nso', 'ts', 've', 'ss', 'nr', 'hz', 'naq', 'ktz',
        # North Africa
        'ar', 'kab', 'tzm', 'cop',
        # Other African
        'mas', 'tuv', 'saq', 'rel', 'gax', 'orc',
        # Major world languages (keeping for completeness)
        'fr', 'pt', 'es', 'de', 'it', 'ru', 'zh', 'ja', 'ko', 'hi'
    }
    
    if target_lang not in supported:
        return text # Let browser handle unsupported langs like Luganda

    # Try LibreTranslate first (if API key available)
    if LIBRE_API_KEY:
        try:
            request_data = {
                "q": text[:500],
                "source": "auto",
                "target": target_lang,
                "format": "text",
                "api_key": LIBRE_API_KEY
            }
            res = requests.post(LIBRE_URL, json=request_data, timeout=3)
            if res.status_code == 200:
                translated = res.json()['translatedText']
                cache.set(cache_key, translated, 604800)
                return translated
        except Exception as e:
            print(f"LibreTranslate error: {e}")

    # Fallback 1: MyMemory API (free, no key required)
    try:
        res = requests.get('https://api.mymemory.translated.net/get', params={
            'q': text[:500],
            'langpair': f'en|{target_lang}'
        }, timeout=5)
        
        if res.status_code == 200:
            data = res.json()
            translated = data.get('responseData', {}).get('translatedText', '')
            match_score = data.get('responseData', {}).get('match', 0)
            
            # Only use if translation quality is good enough (>0.5 match)
            if translated and match_score > 0.5:
                cache.set(cache_key, translated, 604800)
                return translated
    except Exception as e:
        print(f"MyMemory error: {e}")

    # Fallback 2: Google Translate unofficial API (free, no key required)
    try:
        res = requests.get('https://translate.googleapis.com/translate_a/single', params={
            'client': 'gtx',
            'sl': 'en',
            'tl': target_lang,
            'dt': 't',
            'q': text[:500]
        }, timeout=5)
        
        if res.status_code == 200:
            # Parse Google Translate response
            data = res.json()
            if data and len(data) > 0 and len(data[0]) > 0:
                translated = data[0][0][0]  # Extract translated text
                if translated and translated != text:
                    cache.set(cache_key, translated, 604800)
                    return translated
    except Exception as e:
        print(f"Google Translate error: {e}")

    # Final fallback: return original text (browser will offer translation)
    print(f"All translation services failed for {target_lang}, falling back to browser translation")
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

from django.views.decorators.csrf import csrf_exempt

@login_required
def gemini_translate(request):
    """Translate text using multi-service translation - completely free"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '')
        target_language = data.get('target_language', 'en')
        
        if not text:
            return JsonResponse({'error': 'Text required'}, status=400)
        
        # LibreTranslate supported codes
        supported = {
            'sw', 'zu', 'xh', 'af', 'am', 'yo', 'ha', 'ar', 
            'fr', 'pt', 'es', 'de', 'it', 'ru', 'zh', 'ja', 'ko', 'hi'
        }
        
        if target_language not in supported:
            return JsonResponse({
                'success': False,
                'error': f'Language {target_language} not supported by LibreTranslate. Browser translation available.',
                'fallback': 'browser'
            })
        
        # Check cache first
        cache_key = f"translate_{hash(text)}_{target_language}"
        if cached := cache.get(cache_key):
            return JsonResponse({
                'success': True,
                'translated': cached,
                'source_text': text,
                'target_language': target_language,
                'cached': True
            })
        
        # Try LibreTranslate first (if API key available)
        if LIBRE_API_KEY:
            try:
                request_data = {
                    "q": text[:500],
                    "source": "auto",
                    "target": target_language,
                    "format": "text",
                    "api_key": LIBRE_API_KEY
                }
                res = requests.post(LIBRE_URL, json=request_data, timeout=3)
                if res.status_code == 200:
                    translated = res.json()['translatedText']
                    cache.set(cache_key, translated, 604800)
                    return JsonResponse({
                        'success': True,
                        'translated': translated,
                        'source_text': text,
                        'target_language': target_language
                    })
            except Exception as e:
                print(f"LibreTranslate error: {e}")

        # Fallback 1: MyMemory API
        try:
            res = requests.get('https://api.mymemory.translated.net/get', params={
                'q': text[:500],
                'langpair': f'en|{target_language}'
            }, timeout=5)
            
            if res.status_code == 200:
                data = res.json()
                translated = data.get('responseData', {}).get('translatedText', '')
                match_score = data.get('responseData', {}).get('match', 0)
                
                if translated and match_score > 0.5:
                    cache.set(cache_key, translated, 604800)
                    return JsonResponse({
                        'success': True,
                        'translated': translated,
                        'source_text': text,
                        'target_language': target_language
                    })
        except Exception as e:
            print(f"MyMemory error: {e}")

        # Fallback 2: Google Translate unofficial API
        try:
            res = requests.get('https://translate.googleapis.com/translate_a/single', params={
                'client': 'gtx',
                'sl': 'en',
                'tl': target_language,
                'dt': 't',
                'q': text[:500]
            }, timeout=5)
            
            if res.status_code == 200:
                data = res.json()
                if data and len(data) > 0 and len(data[0]) > 0:
                    translated = data[0][0][0]
                    if translated and translated != text:
                        cache.set(cache_key, translated, 604800)
                        return JsonResponse({
                            'success': True,
                            'translated': translated,
                            'source_text': text,
                            'target_language': target_language
                        })
        except Exception as e:
            print(f"Google Translate error: {e}")

        # All services failed - return original with browser fallback info
        return JsonResponse({
            'success': False,
            'error': 'All translation services temporarily unavailable. Browser translation available.',
            'fallback': 'browser',
            'source_text': text,
            'target_language': target_language
        })
        
    except Exception as e:
        print(f"LibreTranslate error: {e}")
        return JsonResponse({
            'error': 'Translation service temporarily unavailable',
            'success': False
        }, status=500)
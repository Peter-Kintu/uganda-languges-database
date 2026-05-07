from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Post, Comment, Like, Connection, Message, Share
from .forms import PostForm
from users.models import CustomUser
from django.conf import settings
from django.template.loader import render_to_string
import json
import os

INVESTOR_CREATE_PASSCODE = getattr(settings, 'INVESTOR_CREATE_PASSCODE', '23882')

@login_required
def social_feed(request):
    # 1. Get the Filter Type from URL parameters (e.g., ?type=images)
    feed_type = request.GET.get('type', 'all')
    
    # Translation parameters
    translate_feed = request.GET.get('translate', 'false').lower() == 'true'
    target_lang = request.GET.get('lang', getattr(request.user, 'language', 'en'))
    if isinstance(target_lang, str):
        target_lang = target_lang.lower()
    
    # 2. Get Global Posts from approved investors that should appear for every user
    global_posts_query = Post.objects.filter(
        author__user_type='investor',
        author__is_approved=True
    ).select_related('author').prefetch_related('comments', 'likes').order_by('-created_at')[:10]
    global_posts = list(global_posts_query)
    global_post_ids = [post.id for post in global_posts]

    # 3. Get ALL ACTIVE POSTS (visible to all logged-in users)
    # Show posts from all users (not just connections) so everyone can see the feed
    regular_posts_query = Post.objects.exclude(id__in=global_post_ids).select_related('author').prefetch_related('comments', 'likes').order_by('-created_at')
    partner_posts_query = Post.objects.filter(author__user_type='investor', author__is_approved=True)\
        .exclude(id__in=global_post_ids).select_related('author').prefetch_related('comments', 'likes').order_by('-created_at')

    # 4. Apply Filtering Logic to BOTH querysets
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

    # 5. Put global/pattern posts at the top for every user
    posts = list(global_posts) + final_feed

    # Paginate feed so we do not load every post at once
    page_number = request.GET.get('page', 1)
    paginator = Paginator(posts, 20)
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)
    posts = list(page_obj.object_list)

    # Handle AJAX requests for infinite scroll
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        html = render_to_string('hotel/posts_partial.html', {'posts': posts, 'request': request})
        return JsonResponse({
            'html': html,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    # Translate posts if requested
    if translate_feed and target_lang != 'en':
        for post in posts:
            if post.content:  # Only translate if there's text
                translated = translate_smart(post.content, target_lang)
                if translated and translated != post.content:
                    post.translated_content = translated
                    post.is_translated = True

    connections = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    )
    following_count = Connection.objects.filter(sender=request.user, status='accepted').count()
    all_users = CustomUser.objects.exclude(id=request.user.id)
    context = {
        'posts': posts,
        'page_obj': page_obj,
        'connections': connections,
        'following_count': following_count,
        'all_users': all_users,
        'current_filter': feed_type,
        'translate_feed': translate_feed,
        'current_lang': target_lang,
    }
    return render(request, 'hotel/social_feed_new.html', context)

@login_required
def create_post(request):
    can_create_direct = request.user.user_type == 'investor' and request.user.is_approved
    passcode_valid = request.session.get('investor_post_access', False)
    allow_create = can_create_direct or passcode_valid
    passcode_error = None

    if request.method == 'GET' and not allow_create:
        query_passcode = request.GET.get('passcode', '').strip()
        if query_passcode and query_passcode == INVESTOR_CREATE_PASSCODE:
            request.session['investor_post_access'] = True
            return redirect('hotel:create_post')

    if request.method == 'POST' and not allow_create:
        submitted_passcode = request.POST.get('passcode', '').strip()
        if submitted_passcode == INVESTOR_CREATE_PASSCODE:
            request.session['investor_post_access'] = True
            return redirect('hotel:create_post')
        passcode_error = 'Invalid 5-digit investor passcode. Contact support@africanaai.info for access.'

    form = PostForm(request.POST or None, request.FILES or None) if allow_create else None

    if request.method == 'POST' and allow_create:
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, 'Post created successfully!')
            return redirect('hotel:social_feed')

    return render(request, 'hotel/create_post.html', {
        'form': form,
        'allow_create': allow_create,
        'passcode_error': passcode_error,
        'support_contact': 'support@africanaai.info',
    })

@login_required
def public_create_post(request):
    form = PostForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        post = form.save(commit=False)
        post.author = request.user
        post.save()
        messages.success(request, 'Post created successfully!')
        return redirect('hotel:social_feed')

    return render(request, 'hotel/post.html', {
        'form': form,
        'support_contact': 's@africanaai.info',
    })

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
            comment = Comment.objects.create(post=post, author=request.user, content=content)
            return JsonResponse({
                'success': True,
                'comment': {
                    'author_initial': comment.author.first_name[:1].upper() if comment.author.first_name else comment.author.username[:1].upper(),
                    'author_name': comment.author.get_full_name() or comment.author.username,
                    'author_username': comment.author.username,
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat(),
                }
            })
    return JsonResponse({'success': False}, status=400)

@login_required
@login_required
def send_connection_request(request, user_id):
    receiver = get_object_or_404(CustomUser, id=user_id)
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

NLLB_URL = "https://sing-sjf2.onrender.com/translate"
LIBRE_URL = "https://libretranslate.com/translate"

# NLLB handles these African languages - LibreTranslate doesn't support well
NLLB_LANGS = {
    # Uganda
    'lg', 'lug', 'nyn', 'ach', 'lgg', 'teo', 'xog', 'ttj', 'nyo', 'laj', 'alz',
    # East Africa
    'sw', 'zu', 'xh', 'yo', 'ha', 'am', 'luo', 'luy', 'kam', 'ki',
    # East/Southern Africa  
    'rw', 'rn', 'so', 'om', 'ti', 'st', 'nso', 'tn', 'ss', 've', 'nr',
    # West/Central/South Africa
    'ny', 'sn', 'tw', 'ak', 'ee', 'fon', 'ln', 'kg', 'mg'
}

# LibreTranslate supported languages (most European + a few others)
LIBRE_SUPPORTED = {
    'en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'pl', 'ru', 'fi', 'hu', 'cs',
    'sv', 'da', 'no', 'ko', 'ja', 'zh', 'ar', 'tr', 'el', 'bg', 'ro', 'hr',
    'sl', 'sk', 'lt', 'et', 'lv', 'he', 'af', 'tl', 'vi', 'th', 'id', 'ms'
}

# Allow UI language codes to be mapped to service-specific translation codes.
LANGUAGE_SERVICE_OVERRIDES = {
    'lg': 'lug',  # Luganda is commonly selected as 'lg' in the UI but NLLB expects ISO 639-3 'lug'
}


def translate_smart(text, target_lang, source_lang='en'):
    """
    Intelligent translation routing with smart service selection:
    1. NLLB for African languages (6s timeout)
    2. LibreTranslate ONLY for supported languages (5s timeout)
    3. MyMemory for everything else + all African languages (4s timeout)
    4. 7-day caching to reduce API load
    5. Graceful fallback to original text on all failures
    """
    target_lang = target_lang.lower() if isinstance(target_lang, str) else target_lang
    source_lang = source_lang.lower() if isinstance(source_lang, str) else source_lang

    # Early returns for no-ops
    if not text or not text.strip() or target_lang == source_lang or target_lang == 'en':
        return text

    # Cache hit = instant return, saves API calls
    cache_key = f"trans_{hash(text)}_{source_lang}_{target_lang}"
    if cached := cache.get(cache_key):
        return cached

    translated = text
    target_code = LANGUAGE_SERVICE_OVERRIDES.get(target_lang, target_lang)

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 1: NLLB for African Languages (Specialist Provider)
    # ═══════════════════════════════════════════════════════════════════════════
    if target_code in NLLB_LANGS and NLLB_URL:
        try:
            r = requests.post(NLLB_URL, json={
                "text": text[:500],
                "target": target_code,
                "source": source_lang
            }, timeout=12)  # Generous timeout for NLLB
            if r.status_code == 200:
                result = r.json()
                translated = result.get('translated', text)
                if translated and translated != text:
                    cache.set(cache_key, translated, 86400)  # Cache 24h
                    return translated
        except requests.Timeout:
            print(f"NLLB timeout for {target_lang} ({target_code}), trying Tier 2...")
        except Exception as e:
            print(f"NLLB error for {target_lang} ({target_code}): {str(e)[:80]}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 2: LibreTranslate for Global Languages (Generalist Provider)
    # Skip for African languages to avoid 400 errors
    # ═══════════════════════════════════════════════════════════════════════════
    if target_code in LIBRE_SUPPORTED and target_code not in NLLB_LANGS:
        try:
            res = requests.post(LIBRE_URL, json={
                "q": text[:500],
                "source": source_lang,
                "target": target_code,
                "format": "text"
            }, timeout=5, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            if res.status_code == 200:
                translated = res.json().get('translatedText', text)
                if translated and translated != text:
                    cache.set(cache_key, translated, 86400)
                    return translated
            elif res.status_code == 429:
                print(f"LibreTranslate rate limited (429) for {target_lang}, falling to Tier 3...")
            elif res.status_code == 400:
                print(f"LibreTranslate doesn't support {target_lang}, falling to Tier 3...")
            else:
                print(f"LibreTranslate error {res.status_code}, falling to Tier 3...")
        except requests.Timeout:
            print(f"LibreTranslate timeout for {target_lang}, falling to Tier 3...")
        except Exception as e:
            print(f"LibreTranslate error: {str(e)[:80]}")

    # ═══════════════════════════════════════════════════════════════════════════
    # TIER 3: MyMemory Universal Fallback (Supports 400+ languages)
    # Used as safety net for all failures in Tier 1 or Tier 2
    # ═══════════════════════════════════════════════════════════════════════════
    try:
        res = requests.get(
            'https://api.mymemory.translated.net/get',
            params={
                'q': text[:500],
                'langpair': f'{source_lang}|{target_code}'
            },
            timeout=5,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        
        if res.status_code == 200:
            result = res.json()
            if result.get('responseStatus') == 200:
                translated = result.get('responseData', {}).get('translatedText', text)
                if translated and translated != text and translated.lower() != 'undefined':
                    cache.set(cache_key, translated, 86400)
                    return translated
            else:
                print(f"MyMemory status {result.get('responseStatus')} for {target_lang}")
    except requests.Timeout:
        print(f"MyMemory timeout for {target_lang}")
    except Exception as e:
        print(f"MyMemory error: {str(e)[:80]}")

    # Final fallback: return original text
    print(f"All translation tiers failed for {target_lang} ({source_lang}), returning original")
    return text

@login_required
def translate_text(request):
    """API endpoint for translating text"""
    text = request.GET.get('text', '')
    target_lang = request.GET.get('target_lang', request.user.language or 'en')
    source_lang = request.GET.get('source_lang', 'en')
    if isinstance(target_lang, str):
        target_lang = target_lang.lower()
    if isinstance(source_lang, str):
        source_lang = source_lang.lower()
    
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
    """Translate text using multi-service translation (NLLB + LibreTranslate + MyMemory)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    
    try:
        data = json.loads(request.body)
        text = data.get('text', '').strip()
        target_language = data.get('target_language', 'en')
        source_language = data.get('source_language', 'en')
        
        if not text:
            return JsonResponse({'error': 'Text required'}, status=400)
        
        # Don't translate if source and target are the same
        if source_language == target_language or target_language == 'en':
            return JsonResponse({
                'success': True,
                'translated': text,
                'source_text': text,
                'target_language': target_language,
                'cached': False,
                'skipped': True
            })
        
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
        
        # Use smart translator with timeout
        try:
            translated = translate_smart(text, target_language, source_language)
        except Exception as e:
            print(f"translate_smart exception: {e}")
            translated = text
        
        # Return results
        if translated and translated != text:
            # Successful translation
            return JsonResponse({
                'success': True,
                'translated': translated,
                'source_text': text,
                'target_language': target_language,
                'source_language': source_language,
                'cached': False
            })
        else:
            # Translation failed or returned same text
            return JsonResponse({
                'success': True,  # Still mark as success to show original
                'translated': text,
                'source_text': text,
                'target_language': target_language,
                'note': 'Translation service unavailable. Showing original text.',
                'cached': False
            })
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        print(f"Translation endpoint error: {e}")
        return JsonResponse({
            'error': 'Translation service error', 
            'success': False
        }, status=500)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.db.models import Q
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from urllib.parse import quote
from .models import Post, Comment, Like, Connection, Message, Share, Community, CommunityMessage
from .forms import PostForm
from users.models import CustomUser
from django.conf import settings
from django.template.loader import render_to_string
import requests
import json
import os
import hashlib

INVESTOR_CREATE_PASSCODE = getattr(settings, 'INVESTOR_CREATE_PASSCODE', '23882')


def _safe_cache_get(key, default=None):
    try:
        return cache.get(key, default)
    except Exception as e:
        print(f"Cache get failed: {e}")
        return default


def _safe_cache_set(key, value, timeout=None):
    try:
        cache.set(key, value, timeout)
    except Exception as e:
        print(f"Cache set failed: {e}")


def _is_suspicious_text(t, original_len):
    if not t or not isinstance(t, str):
        return True
    s = t.strip()
    if len(s) == 0:
        return True
    # too long or contains unrelated tokens (quick heuristics)
    if len(s) > max(2000, original_len * 15):
        return True
    lowered = s.lower()
    # Count only if multiple spam indicators present
    suspicious_count = sum(1 for tok in ['http://', 'https://', 'www.'] if tok in lowered)
    if suspicious_count > 1:
        return True
    return False


def _google_translate(text, source_lang, target_lang):
    if not text or not isinstance(text, str) or not target_lang:
        return None

    text = text.strip()
    if not text:
        return None
    source = source_lang if source_lang != 'auto' else 'auto'
    params = {
        'client': 'gtx',
        'sl': source,
        'tl': target_lang,
        'dt': 't',
        'q': text,
    }
    try:
        res = requests.get(
            GOOGLE_TRANSLATE_BASE,
            params=params,
            timeout=20,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'application/json',
            }
        )
        if res.status_code != 200:
            print(f"Google fallback status {res.status_code} for {target_lang}: {res.text[:200]}")
            return None

        data = res.json()
        if not isinstance(data, list) or not data or not isinstance(data[0], list):
            return None

        translated_segments = []
        for item in data[0]:
            if isinstance(item, list) and item and isinstance(item[0], str):
                segment = item[0].strip()
                if segment:
                    translated_segments.append(segment)

        translated = ' '.join(translated_segments).strip()
        if translated and isinstance(translated, str) and len(translated) > 2 and translated != text and not _is_suspicious_text(translated, len(text)):
            return translated
    except Exception as e:
        print(f"Google fallback error for {target_lang}: {str(e)[:150]}")

    return None


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

    # Translate posts if requested
    if translate_feed and target_lang != 'en':
        for post in posts:
            try:
                if post.content:  # Only translate if there's text
                    translated = translate_smart(post.content, target_lang, 'en')
                    if translated and isinstance(translated, str) and translated.strip() and translated != post.content:
                        post.translated_content = translated
                        post.is_translated = True
            except Exception as e:
                print(f"Translation error for post {post.id}: {str(e)[:100]}")
                post.is_translated = False

    # Handle AJAX requests for infinite scroll
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        html = render_to_string('hotel/posts_partial.html', {
            'posts': posts,
            'request': request,
            'current_lang': target_lang,
        })
        return JsonResponse({
            'html': html,
            'has_next': page_obj.has_next(),
            'next_page': page_obj.next_page_number() if page_obj.has_next() else None,
        })

    connections = Connection.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user),
        status='accepted'
    )
    following_count = Connection.objects.filter(sender=request.user, status='accepted').count()
    all_users = CustomUser.objects.exclude(id=request.user.id)
    
    # Add follower count and following status to each post author
    author_ids = set(post.author.id for post in posts)
    follower_counts = {}
    following_status = {}
    
    for author_id in author_ids:
        follower_counts[author_id] = Connection.objects.filter(
            receiver_id=author_id, 
            status='accepted'
        ).count()
        following_status[author_id] = Connection.objects.filter(
            sender=request.user,
            receiver_id=author_id,
            status='accepted'
        ).exists()
    
    for post in posts:
        post.author.follower_count = follower_counts.get(post.author.id, 0)
        post.author.is_following = following_status.get(post.author.id, False)
    
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

SUNBIRD_URL = getattr(settings, 'SUNBIRD_API_URL', 'https://api.sunbird.ai')
SUNBIRD_API_KEY = getattr(settings, 'SUNBIRD_API_KEY', None)
NLLB_URL = getattr(settings, 'NLLB_API_URL', None) or 'https://sing-sjf2.onrender.com/translate'
LIBRE_URL = "https://libretranslate.com/translate"
LIBRE_ALT_URL = getattr(settings, 'LIBRE_ALT_URL', 'https://libretranslate.de/translate')
LIBRE_API_KEY = getattr(settings, 'LIBRE_API_KEY', None)

# Sunbird supports these African/Ugandan languages.
SUNBIRD_LANGS = {
    'ach', 'eng', 'ibo', 'lgg', 'lug', 'nyn', 'swa', 'teo', 'xog', 'kin', 'myx',
    'adh', 'alz', 'bfa', 'cgg', 'gwr', 'kdi', 'kdj', 'keo', 'koo', 'kpz',
    'laj', 'lsm', 'luc', 'mhi', 'pok', 'rub', 'ruc', 'rwm', 'tlj', 'nuj', 'nyo'
}

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

GOOGLE_TRANSLATE_BASE = 'https://translate.googleapis.com/translate_a/single'

# Allow UI language codes to be mapped to service-specific translation codes.
LANGUAGE_SERVICE_OVERRIDES = {
    'lg': 'lug',  # Luganda is commonly selected as 'lg' in the UI but NLLB expects ISO 639-3 'lug'
}


def translate_smart(text, target_lang, source_lang='en'):
    """
    Intelligent translation routing with smart service selection:
    1. Sunbird for Uganda languages
    2. NLLB for African languages
    3. LibreTranslate for broadly supported languages
    4. MyMemory as a final fallback
    5. 7-day caching to reduce API load
    6. Graceful fallback to original text on all failures
    """
    target_lang = target_lang.lower() if isinstance(target_lang, str) else target_lang
    source_lang = source_lang.lower() if isinstance(source_lang, str) else source_lang
    service_source_lang = 'en' if source_lang == 'auto' else source_lang

    # Early returns for no-ops
    if not text or not text.strip() or target_lang == source_lang:
        return text

    # Prepare common values and helpers up-front
    target_code = LANGUAGE_SERVICE_OVERRIDES.get(target_lang, target_lang)
    if isinstance(target_code, str):
        target_code = target_code.lower().strip()
    if isinstance(source_lang, str):
        source_lang = source_lang.lower().strip()

    # Use stable cache key (hash can vary between runs)
    text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
    cache_key = f"trans_{text_hash}_{source_lang}_{target_lang}"
    cached = _safe_cache_get(cache_key)
    if cached is not None and isinstance(cached, str) and len(cached) > 0:
        return cached

    def _try_sunbird():
        if not SUNBIRD_API_KEY:
            print("Sunbird API key not configured, skipping Sunbird translation")
            return None

        # Sunbird doesn't support 'auto' - always use 'eng' or map source lang
        if source_lang in {'en', 'eng', 'auto'}:
            api_source = 'eng'
        else:
            api_source = source_lang
        
        # Validate that target language is supported by Sunbird
        if target_code not in SUNBIRD_LANGS and target_lang not in SUNBIRD_LANGS:
            print(f"Target language {target_code} not supported by Sunbird")
            return None
            
        payload = {
            'source_language': api_source,
            'target_language': target_code,
            'text': text
        }
        request_url = SUNBIRD_URL.rstrip('/') + '/tasks/translate'
        res = requests.post(
            request_url,
            json=payload,
            timeout=30,
            headers={
                'Authorization': f'Bearer {SUNBIRD_API_KEY}',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
        )
        if res.status_code != 200:
            if res.status_code == 422:
                print(f"Sunbird validation error for {target_code}: {res.text[:300]}")
            elif res.status_code >= 500:
                print(f"Sunbird server error {res.status_code}")
            else:
                print(f"Sunbird status {res.status_code} for {target_code}: {res.text[:200]}")
            return None

        try:
            data = res.json()
        except Exception as e:
            print(f"Sunbird JSON parse error: {str(e)[:100]}")
            return None
        translated_text = (
            data.get('output', {}).get('translated_text') or
            data.get('output', {}).get('translatedText') or
            data.get('output', {}).get('text')
        )
        if isinstance(translated_text, str) and translated_text.strip() and translated_text != text and not _is_suspicious_text(translated_text, len(text)):
            return translated_text
        print(f"Sunbird returned suspicious/empty result for {target_code}: {json.dumps(data)[:400]}")
        return None

    def _try_nllb():
        if not NLLB_URL:
            print("NLLB API URL not configured, skipping NLLB translation")
            return None
        request_url = NLLB_URL.rstrip('/') + '/'
        # NLLB expects proper language codes, default to 'en' for auto
        source_code = 'en' if service_source_lang in {'en', 'eng', 'auto'} else service_source_lang
        payload = {
            'source': source_code,
            'target': target_code,
            'text': text
        }
        try:
            res = requests.post(
                request_url,
                json=payload,
                timeout=100,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                    'Accept': 'application/json',
                    'Content-Type': 'application/json'
                }
            )
        except requests.Timeout:
            print(f"NLLB timeout for {target_code} (possible Render cold start)")
            return None
        except Exception as e:
            print(f"NLLB request error for {target_code}: {str(e)[:120]}")
            return None

        if res.status_code != 200:
            if res.status_code == 403:
                print(f"NLLB access forbidden (rate limited or IP blocked) for {target_code}")
            elif res.status_code >= 500:
                print(f"NLLB server error {res.status_code}")
            else:
                print(f"NLLB status {res.status_code} for {target_code}: {res.text[:100]}")
            return None

        try:
            data = res.json()
        except Exception as e:
            print(f"NLLB JSON parse error for {target_code}: {e}")
            return None

        translated_text = data.get('translated_text') or data.get('translation') or data.get('translated')
        if isinstance(translated_text, str) and translated_text.strip() and translated_text != text and not _is_suspicious_text(translated_text, len(text)):
            return translated_text
        print(f"NLLB returned suspicious/empty result for {target_code}: {json.dumps(data)[:400]}")
        return None

    def _try_libre():
        if target_code not in LIBRE_SUPPORTED and target_lang not in LIBRE_SUPPORTED:
            return None

        def _call_libre(url):
            # LibreTranslate expects 'auto' for auto-detect, otherwise use language code
            libre_source = service_source_lang if service_source_lang in {'auto', 'en', 'eng'} else service_source_lang
            if libre_source == 'eng':
                libre_source = 'en'
            payload = {
                'q': text,
                'source': libre_source,
                'target': target_code,
                'format': 'text'
            }
            if LIBRE_API_KEY:
                payload['api_key'] = LIBRE_API_KEY
            res = requests.post(
                url,
                json=payload,
                timeout=10,
                headers={
                    'User-Agent': 'Mozilla/5.0',
                    'Content-Type': 'application/json'
                }
            )
            return res

        for url in [LIBRE_URL, LIBRE_ALT_URL]:
            try:
                res = _call_libre(url)
                if res.status_code != 200:
                    if res.status_code == 400 and 'api key' in res.text.lower():
                        print(f"LibreTranslate {url} requires API key for {target_code}")
                        continue
                    if res.status_code == 429:
                        print(f"LibreTranslate rate limited at {url}")
                        continue
                    if res.status_code == 403:
                        print(f"LibreTranslate access forbidden at {url}")
                        continue
                    if res.status_code >= 500:
                        print(f"LibreTranslate server error {res.status_code} at {url}")
                    continue
                data = res.json()
                translated_text = data.get('translatedText') or data.get('translation') or data.get('translated')
                if isinstance(translated_text, str) and translated_text.strip() and translated_text != text and not _is_suspicious_text(translated_text, len(text)):
                    return translated_text
            except requests.Timeout:
                print(f"LibreTranslate timeout for {target_code} at {url}")
            except Exception as e:
                print(f"LibreTranslate error for {target_code} at {url}: {str(e)[:120]}")
        return None

    def _try_mymemory():
        if not target_code:
            return None
        # MyMemory doesn't support 'auto' source, default to 'en'
        mymem_source = 'en' if service_source_lang in {'auto', 'en', 'eng'} else service_source_lang
        try:
            res = requests.get(
                'https://api.mymemory.translated.net/get',
                params={
                    'q': text[:500],
                    'langpair': f'{mymem_source}|{target_code}'
                },
                timeout=8,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            if res.status_code != 200:
                if res.status_code == 403:
                    print(f"MyMemory access forbidden (rate limited or IP blocked) for {target_lang}")
                elif res.status_code >= 500:
                    print(f"MyMemory server error {res.status_code}")
                else:
                    print(f"MyMemory status {res.status_code} for {target_lang}")
                return None
            result = res.json()
            if result.get('responseStatus') == 200:
                translated = result.get('responseData', {}).get('translatedText', '')
                if translated and isinstance(translated, str) and translated.strip() and translated != text and translated.lower() != 'undefined' and not _is_suspicious_text(translated, len(text)):
                    return translated
            else:
                print(f"MyMemory status {result.get('responseStatus')} for {target_lang}")
        except requests.Timeout:
            print(f"MyMemory timeout for {target_lang}")
        except Exception as e:
            print(f"MyMemory error: {str(e)[:80]}")
        return None

    def _try_google():
        try:
            for code in [target_lang, target_code]:
                if not code:
                    continue
                text_candidate = _google_translate(text, source_lang, code)
                if text_candidate:
                    return text_candidate
            return None
        except Exception as e:
            print(f"Google translate fallback error for {target_lang}: {e}")
            return None

    if target_code in SUNBIRD_LANGS or target_lang in SUNBIRD_LANGS:
        translated_text = _try_sunbird()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_mymemory()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_nllb()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_libre()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_google()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
    else:
        translated_text = _try_mymemory()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_libre()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text
        translated_text = _try_google()
        if translated_text:
            _safe_cache_set(cache_key, translated_text, 604800)
            return translated_text

    print(f"All translation tiers failed for {target_lang} ({source_lang}), returning original")
    return text

@login_required
def translate_text(request):
    """API endpoint for translating text"""
    try:
        text = request.GET.get('text', '').strip()
        target_lang = request.GET.get('target_lang', getattr(request.user, 'language', 'en') or 'en')
        source_lang = request.GET.get('source_lang', 'en')
        
        if isinstance(target_lang, str):
            target_lang = target_lang.lower().strip()
        if isinstance(source_lang, str):
            source_lang = source_lang.lower().strip()
        
        if not text:
            return JsonResponse({'error': 'Text required', 'translated': ''}, status=400)
        
        if len(text) > 5000:
            return JsonResponse({'error': 'Text too long (max 5000 chars)', 'translated': text}, status=400)
        
        translated = translate_smart(text, target_lang, source_lang)
        if not translated:
            translated = text
        
        return JsonResponse({'translated': translated, 'success': True})
    except Exception as e:
        print(f"translate_text error: {str(e)[:150]}")
        return JsonResponse({'error': str(e)[:100], 'translated': ''}, status=500)

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
                # messages.success(request, f'Message sent to {receiver.username}!')
                return redirect('hotel:inbox')
    return JsonResponse({'success': False}, status=400)

@login_required
def inbox(request):
    return redirect('hotel:inbox_messages')

@login_required
def inbox_messages(request):
    messages_list = Message.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by('-created_at')

    conversations = {}
    for msg in messages_list:
        partner = msg.receiver if msg.sender == request.user else msg.sender
        if partner.id not in conversations:
            conversations[partner.id] = {
                'grouper': partner,
                'list': []
            }
        conversations[partner.id]['list'].append(msg)

    message_groups = list(conversations.values())
    unread_messages = messages_list.filter(receiver=request.user, is_read=False)[:5]
    unread_messages_count = messages_list.filter(receiver=request.user, is_read=False).count()
    communities = Community.objects.filter(members=request.user).order_by('-created_at')
    notifications = Message.objects.none()

    return render(request, 'hotel/inbox.html', {
        'message_groups': message_groups,
        'messages': messages_list,
        'communities': communities,
        'unread_messages': unread_messages,
        'unread_messages_count': unread_messages_count,
        'notifications': notifications,
    })

@login_required
def inbox_communities(request):
    messages_list = Message.objects.filter(receiver=request.user).order_by('-created_at')
    communities = Community.objects.filter(members=request.user).order_by('-created_at')
    unread_messages = messages_list.filter(is_read=False)[:5]
    unread_count = messages_list.filter(is_read=False).count()
    return render(request, 'hotel/inbox_communities.html', {
        'messages': messages_list,
        'communities': communities,
        'unread_messages': unread_messages,
        'unread_count': unread_count,
    })

@login_required
def inbox_notifications(request):
    messages_list = Message.objects.filter(receiver=request.user).order_by('-created_at')
    communities = Community.objects.filter(members=request.user).order_by('-created_at')
    unread_messages = messages_list.filter(is_read=False)[:5]
    unread_count = messages_list.filter(is_read=False).count()
    return render(request, 'hotel/inbox_notifications.html', {
        'messages': messages_list,
        'communities': communities,
        'unread_messages': unread_messages,
        'unread_count': unread_count,
    })

@login_required
def mark_message_read(request, message_id):
    if request.method == 'POST':
        message = get_object_or_404(Message, id=message_id, receiver=request.user)
        message.is_read = True
        message.save()
        
        # Check if it's an AJAX request
        is_ajax = (
            request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
            'application/json' in request.headers.get('Accept', '')
        )
        
        if is_ajax:
            return JsonResponse({'success': True})
        
        return redirect('hotel:inbox')
    return JsonResponse({'success': False}, status=400)

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
        if source_language == target_language:
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
        cached = _safe_cache_get(cache_key)
        if cached:
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

@login_required
def conversation(request, user_id):
    other_user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        attachment = request.FILES.get('attachment')
        if content or attachment:
            Message.objects.create(
                sender=request.user,
                receiver=other_user,
                content=content,
                attachment=attachment
            )
            # Mark messages as read when replying
            Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
        return redirect('hotel:conversation', user_id=user_id)
    
    # Get messages between the two users
    messages = Message.objects.filter(
        (Q(sender=request.user) & Q(receiver=other_user)) |
        (Q(sender=other_user) & Q(receiver=request.user))
    ).order_by('created_at')
    
    # Mark received messages as read
    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True)
    
    return render(request, 'hotel/conversation.html', {
        'other_user': other_user,
        'messages': messages
    })

@login_required
def create_community(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            community = Community.objects.create(name=name, description=description, creator=request.user)
            community.members.add(request.user)
            messages.success(request, f'Community "{name}" created successfully!')
            return redirect('hotel:community_conversation', community_id=community.id)
    return render(request, 'hotel/create_community.html')

def join_community(request, invite_link):
    community = get_object_or_404(Community, invite_link=invite_link)
    if not request.user.is_authenticated:
        next_url = quote(request.path)
        return redirect(f"{settings.LOGIN_URL}?next={next_url}")
    if request.user not in community.members.all():
        community.members.add(request.user)
        messages.success(request, f'Joined community "{community.name}"!')
    return redirect('hotel:community_conversation', community_id=community.id)

@login_required
def community_conversation(request, community_id):
    community = get_object_or_404(Community, id=community_id, members=request.user)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        attachment = request.FILES.get('attachment')
        if content or attachment:
            CommunityMessage.objects.create(
                community=community,
                sender=request.user,
                content=content,
                attachment=attachment
            )
        return redirect('hotel:community_conversation', community_id=community_id)
    
    messages = community.messages.all().order_by('created_at')
    return render(request, 'hotel/community_conversation.html', {
        'community': community,
        'messages': messages
    })

@login_required
def follow_user(request, user_id):
    user_to_follow = get_object_or_404(CustomUser, id=user_id)
    
    # Check if it's an AJAX request first
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '')
    )
    
    if user_to_follow == request.user:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': 'You cannot follow yourself.'
            })
        messages.error(request, 'You cannot follow yourself.')
        return redirect(request.META.get('HTTP_REFERER', 'hotel:social_feed'))
    
    connection, created = Connection.objects.get_or_create(
        sender=request.user,
        receiver=user_to_follow,
        defaults={'status': 'accepted'}
    )
    if created:
        message = f'You are now following {user_to_follow.username}!'
    else:
        message = f'You are already following {user_to_follow.username}.'
    
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': message,
            'is_following': True,
            'follower_count': Connection.objects.filter(receiver=user_to_follow, status='accepted').count()
        })
    
    # messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'hotel:social_feed'))

@login_required
def unfollow_user(request, user_id):
    user_to_unfollow = get_object_or_404(CustomUser, id=user_id)
    
    # Check if it's an AJAX request first
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '')
    )
    
    if user_to_unfollow == request.user:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'message': 'You cannot unfollow yourself.'
            })
        messages.error(request, 'You cannot unfollow yourself.')
        return redirect(request.META.get('HTTP_REFERER', 'hotel:social_feed'))
    
    Connection.objects.filter(sender=request.user, receiver=user_to_unfollow).delete()
    message = f'Unfollowed {user_to_unfollow.username}.'
    
    if is_ajax:
        return JsonResponse({
            'success': True,
            'message': message,
            'is_following': False,
            'follower_count': Connection.objects.filter(receiver=user_to_unfollow, status='accepted').count()
        })
    
    # messages.success(request, message)
    return redirect(request.META.get('HTTP_REFERER', 'hotel:social_feed'))
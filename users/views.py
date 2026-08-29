import os
import json
import logging
import requests
import time
import base64
from decimal import Decimal
from datetime import datetime, timedelta, date
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.db import IntegrityError, models
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import TemplateDoesNotExist
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_pesapal_config():
    base_url = os.getenv('PESAPAL_BASE_URL', 'https://pay.pesapal.com/pesapalv3')
    base_url = base_url.rstrip('/')
    if base_url.endswith('/api'):
        base_url = base_url[:-4]
    if base_url == 'https://pay.pesapal.com/pesapalv3':
        base_url = 'https://pay.pesapal.com/v3'
    return {
        'base_url': base_url,
        'consumer_key': os.getenv('PESAPAL_CONSUMER_KEY', ''),
        'consumer_secret': os.getenv('PESAPAL_CONSUMER_SECRET', ''),
    }


def _pesapal_auth_header():
    config = _get_pesapal_config()
    credentials = f"{config['consumer_key']}:{config['consumer_secret']}".encode('utf-8')
    token = base64.b64encode(credentials).decode('utf-8')
    return {'Authorization': f'Basic {token}'}


def _pesapal_access_token():
    config = _get_pesapal_config()
    if not config['consumer_key'] or not config['consumer_secret']:
        raise ValueError('Pesapal consumer key and secret must be configured.')

    base_url = config['base_url'].rstrip('/')
    url = f"{base_url}/api/Auth/RequestToken"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    payload = {
        'consumer_key': config['consumer_key'],
        'consumer_secret': config['consumer_secret'],
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if not getattr(response, 'ok', response.status_code < 400):
            response.raise_for_status()
        auth_response = response.json()
    except requests.exceptions.RequestException as exc:
        logger.warning('Pesapal token request failed: %s', exc)
        raise RuntimeError(f'Pesapal token request failed: {exc}') from exc

    token = auth_response.get('token') if isinstance(auth_response, dict) else None
    if not token:
        raise ValueError('Pesapal authentication did not return a bearer token.')
    return token


def _pesapal_request(method, path, json_data=None, timeout=20, access_token=None):
    config = _get_pesapal_config()
    base_url = config['base_url'].rstrip('/')
    if base_url.endswith('/api'):
        base_url = base_url[:-4]
    url = f"{base_url}/api/{path.lstrip('/')}"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    payload = json_data

    if path.lstrip('/') == 'Auth/RequestToken':
        payload = {
            'consumer_key': config['consumer_key'],
            'consumer_secret': config['consumer_secret'],
        }
    elif access_token:
        headers['Authorization'] = f'Bearer {access_token}'
    elif path.lstrip('/').startswith('Transactions/') or path.lstrip('/').startswith('Settlement/'):
        access_token = _pesapal_access_token()
        headers['Authorization'] = f'Bearer {access_token}'

    method = method.lower()

    try:
        if method == 'post':
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
        else:
            response = requests.get(url, headers=headers, params=json_data, timeout=timeout)

        if not getattr(response, 'ok', response.status_code < 400):
            response.raise_for_status()

        try:
            return response.json()
        except ValueError:
            return {'status': 'ok'}
    except requests.exceptions.RequestException as exc:
        logger.warning('Pesapal request failed for %s: %s', path, exc)
        raise RuntimeError(f'Pesapal request failed for {path}: {exc}') from exc


# Google auth token verification
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

# Cerebras SDK imports
from cerebras.cloud.sdk import Cerebras

# Custom Forms and Models
from .models import CustomUser, Experience, Education, Skill, SocialConnection, PayoutRequest, UserSubscription, PesapalPayment 
# Import cross-app models for profile aggregates (keep optional to avoid hard failures)
try:
    from hotel.models import Post, Like, Comment, Share, Connection, FeedImpression
except Exception:
    Post = None
    Like = None
    Comment = None
    Share = None
    Connection = None
    FeedImpression = None
from .forms import CustomUserCreationForm, ProfileEditForm
from django.contrib.auth import get_user_model

User = get_user_model()

# Safely import eshop models
try:
    from eshop.models import Product, CartItem, Order 
except ImportError:
    Product = None
    CartItem = None
    Order = None

# ==============================================================================
# UTILITY / INFRASTRUCTURE VIEWS
# ==============================================================================

def google_verification(request):
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Allow: /go",
        "Allow: /go/",
        "Allow: /profile/",
        "Allow: /social/",
        "Allow: /social/reel/",
        "Allow: /jobs/",
        "Allow: /languages/",
        "Allow: /eshop/",
        "# Disallow admin and sensitive areas",
        "Disallow: /admin/",
        "Disallow: /accounts/",
        "Disallow: /api/",
        "Disallow: /cart/",
        "Disallow: /checkout/",
        f"Sitemap: https://{settings.DEFAULT_DOMAIN}/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def tts_proxy(request):
    text = request.GET.get('text', '')
    lang = request.GET.get('lang', 'en')
    if not text:
        return HttpResponse("No text provided", status=400)
    
    tts_url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={text}&tl={lang}&client=tw-ob"
    try:
        response = requests.get(tts_url, stream=True, timeout=5)
        return HttpResponse(response.content, content_type="audio/mpeg")
    except Exception as e:
        return HttpResponse(f"Error: {str(e)}", status=500)

# ==============================================================================
# AUTHENTICATION VIEWS
# ==============================================================================

def user_login(request):
    ref = request.GET.get('ref')
    if ref:
        request.session['referrer'] = ref
    if request.user.is_authenticated:
        return redirect('hotel:social_feed')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.POST.get('next') or request.GET.get('next')
            return redirect(next_url or reverse('hotel:social_feed')) 
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()


    google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    context = {
        'form': form,
        'next': request.GET.get('next', ''),
        'google_client_id': google_client_id,
    }

    try:
        return render(request, 'users/login.html', context)
    except TemplateDoesNotExist:
        return render(request, 'login.html', context)


@csrf_exempt
def google_auth_receiver(request):
    if request.method != 'POST':
        return HttpResponse('POST required', status=405)

    token = request.POST.get('credential')
    if not token:
        return HttpResponse('Missing credential', status=400)

    next_url = request.POST.get('next') or request.GET.get('next') or ''
    if next_url:
        if next_url.startswith('/'):
            # relative URL, allow
            pass
        elif not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            next_url = ''

    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    if not client_id:
        return HttpResponse('Google client ID not configured', status=500)

    try:
        idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
        if idinfo.get('iss') not in ['accounts.google.com', 'https://accounts.google.com']:
            raise ValueError('Wrong issuer.')

        email = idinfo.get('email')
        if not email:
            return HttpResponse('Email is required', status=400)

        first_name = idinfo.get('given_name', '')
        last_name = idinfo.get('family_name', '')

        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'username': email,
                'first_name': first_name,
                'last_name': last_name,
            }
        )
        if created:
            user.save()

        login(request, user)
        return redirect(next_url or reverse('hotel:social_feed'))

    except ValueError as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google auth ValueError: {str(e)}, client_id: {client_id[:10]}...")
        return HttpResponse('Invalid token', status=403)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google auth error: {str(e)}")
        return HttpResponse(str(e), status=400)



def user_register(request):
    ref = request.GET.get('ref')
    if ref:
        request.session['referrer'] = ref
    if request.user.is_authenticated:
        return redirect('hotel:social_feed')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            referrer_username = request.session.get('referrer')
            if referrer_username:
                try:
                    referrer_user = User.objects.get(username=referrer_username)
                    if hasattr(user, 'referrer'):
                        user.referrer = referrer_user
                except User.DoesNotExist:
                    pass 
            try:
                user.save()
            except IntegrityError as e:
                if 'username' in str(e).lower():
                    form.add_error('username', 'A user with that username already exists.')
                else:
                    form.add_error(None, 'Unable to complete registration. Please try again.')
            else:
                login(request, user)
                if 'referrer' in request.session:
                    del request.session['referrer']
                messages.success(request, "Registration successful. Welcome!")
                return redirect('hotel:social_feed')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = CustomUserCreationForm()
    google_client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    context = {
        'form': form,
        'google_client_id': google_client_id,
        'next': request.GET.get('next', ''),
    }
    try:
        return render(request, 'users/register.html', context)
    except TemplateDoesNotExist:
        return render(request, 'register.html', context)

@login_required
def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:user_login')


@login_required
@csrf_exempt
def pesapal_start_checkout(request):
    if request.method not in {'POST', 'GET'}:
        return JsonResponse({'status': 'error', 'message': 'Method not allowed.'}, status=405)

    subscription, _ = UserSubscription.objects.get_or_create(
        user=request.user,
        defaults={'status': 'pending', 'plan_name': 'pro_business'},
    )
    if not subscription.is_active:
        subscription.status = 'pending'
        subscription.is_active = False
        subscription.save(update_fields=['status', 'is_active'])

    amount = Decimal(getattr(settings, 'PESAPAL_PRO_AMOUNT', '30000.00'))
    order_id = f"pro-{request.user.id}-{int(time.time())}"
    callback_url = getattr(settings, 'PESAPAL_CALLBACK_URL', request.build_absolute_uri(reverse('users:pesapal_callback')))
    notification_url = getattr(settings, 'PESAPAL_IPN_URL', request.build_absolute_uri(reverse('users:pesapal_ipn')))

    payment = PesapalPayment.objects.create(
        user=request.user,
        subscription=subscription,
        order_id=order_id,
        amount=amount,
        currency=getattr(settings, 'PESAPAL_CURRENCY', 'UGX'),
        description='30-Day Pro Business Pass',
        redirect_url=callback_url,
        status='PENDING',
    )

    try:
        auth_payload = _pesapal_request('post', 'Auth/RequestToken')
        token = auth_payload.get('token') if isinstance(auth_payload, dict) else None
        if not token:
            raise ValueError('Pesapal authentication did not return a bearer token.')

        submit_payload = {
            'id': order_id,
            'currency': payment.currency,
            'amount': f"{payment.amount:.2f}",
            'description': payment.description,
            'callback_url': callback_url,
            'notification_id': notification_url,
            'billing_address': {
                'email_address': request.user.email or f"{request.user.username}@example.com",
                'phone_number': '',
                'country_code': 'UG',
                'first_name': request.user.first_name or request.user.username,
                'last_name': request.user.last_name or 'User',
            },
        }
        order_payload = _pesapal_request(
            'post',
            'Transactions/SubmitOrderRequest',
            json_data=submit_payload,
            access_token=token,
        )
    except Exception as exc:
        payment.status = 'FAILED'
        payment.save(update_fields=['status'])
        subscription.status = 'failed'
        subscription.is_active = False
        subscription.save(update_fields=['status', 'is_active'])
        logger.exception('Pesapal checkout creation failed: %s', exc)
        messages.error(request, 'Unable to start Pesapal checkout right now.')
        return redirect('users:profile')

    payment.tracking_id = order_payload.get('order_tracking_id') or order_payload.get('OrderTrackingId')
    payment.redirect_url = order_payload.get('redirect_url') or order_payload.get('RedirectUrl') or callback_url
    payment.save(update_fields=['tracking_id', 'redirect_url'])

    return redirect(payment.redirect_url or reverse('users:profile'))


@csrf_exempt
def pesapal_ipn(request):
    tracking_id = request.POST.get('OrderTrackingId') or request.POST.get('order_tracking_id')
    if not tracking_id:
        return JsonResponse({'status': 'error', 'message': 'Missing tracking id.'}, status=400)

    payment = get_object_or_404(PesapalPayment, tracking_id=tracking_id)

    try:
        auth_payload = _pesapal_request('post', 'Auth/RequestToken')
        token = auth_payload.get('token') if isinstance(auth_payload, dict) else None
        if not token:
            raise ValueError('Pesapal authentication did not return a bearer token.')

        transaction_payload = _pesapal_request(
            'post',
            'Transactions/GetTransactionStatus',
            json_data={'orderTrackingId': tracking_id},
            access_token=token,
        )
    except Exception as exc:
        logger.exception('Pesapal IPN verification failed: %s', exc)
        return JsonResponse({'status': 'error', 'message': 'Unable to verify payment status.'}, status=502)

    status = str(transaction_payload.get('status') or transaction_payload.get('Status') or '').upper()
    if status in {'COMPLETED', 'PAID', 'SUCCESS', 'SUCCESSFUL'}:
        payment.status = 'PAID'
        payment.subscription.status = 'active'
        payment.subscription.is_active = True
        payment.subscription.start_date = datetime.now()
        payment.subscription.end_date = datetime.now() + timedelta(days=30)
        payment.subscription.save(update_fields=['status', 'is_active', 'start_date', 'end_date'])
    else:
        payment.status = 'FAILED' if status in {'FAILED', 'CANCELLED', 'CANCELED'} else payment.status
        payment.subscription.status = 'failed' if payment.status == 'FAILED' else payment.subscription.status
        payment.subscription.is_active = False
        payment.subscription.save(update_fields=['status', 'is_active'])
    payment.save(update_fields=['status'])

    return JsonResponse({'status': 'OK', 'message': 'Pesapal notification processed.'})


@login_required
def pesapal_callback(request):
    tracking_id = request.GET.get('OrderTrackingId') or request.GET.get('orderTrackingId')
    if tracking_id:
        payment = PesapalPayment.objects.filter(tracking_id=tracking_id).first()
        if payment:
            context = {'payment': payment, 'is_success': payment.status == 'PAID'}
            return render(request, 'users/pesapal_callback.html', context)
    return render(request, 'users/pesapal_callback.html', {'payment': None, 'is_success': False})

# ==============================================================================
# PROFILE & REFERRAL DASHBOARD
# ==============================================================================

@login_required
def user_profile(request):
    user = request.user
    experiences = Experience.objects.filter(user=user).order_by('-start_date')
    educations = Education.objects.filter(user=user).order_by('-end_date')
    skills = Skill.objects.filter(user=user)
    social_connections = SocialConnection.objects.filter(user=user)
    successful_referrals = []
    referral_earnings = 0
    if Order:
        successful_referrals = Order.objects.filter(referrer=user, status='Completed')
        referral_earnings = successful_referrals.aggregate(Sum('total_commission'))['total_commission__sum'] or 0
    base_url = request.build_absolute_uri(reverse('users:user_register'))
    referral_link = f"{base_url}?ref={user.username}"
    # --- Profile aggregates ---
    # Connections / followers
    followers_count = 0
    following_count = 0
    connections_count = 0
    if Connection:
        followers_count = Connection.objects.filter(receiver=user, status='accepted').count()
        following_count = Connection.objects.filter(sender=user, status='accepted').count()
        connections_count = Connection.objects.filter(models.Q(sender=user) | models.Q(receiver=user), status='accepted').count()

    # Posts and engagements
    user_posts = []
    posts_count = 0
    impressions = None
    watch_hours = None
    try:
        if Post:
            user_posts = Post.objects.filter(author=user).order_by('-created_at')
            posts_count = user_posts.count()

            if FeedImpression:
                impressions = FeedImpression.objects.filter(
                    content_type='post', object_id__in=user_posts.values('id')
                ).count()
            else:
                impressions = user_posts.aggregate(Sum('impressions'))['impressions__sum'] or 0

            likes_count = Like.objects.filter(post__author=user).count() if Like else 0
            job_ad_watch_count = getattr(user, 'post_ad_watch_count', 0)
            can_request_payout = (
                (impressions or 0) >= 10000 and
                likes_count >= 100 and
                job_ad_watch_count >= 100
            )
            post_earnings_amount = 10 if can_request_payout else 0
            pending_payout_request = PayoutRequest.objects.filter(user=user, status='pending').order_by('-created_at').first()

            # Watch time aggregation if available on Post model
            if hasattr(Post, 'watch_seconds'):
                total_seconds = user_posts.aggregate(Sum('watch_seconds'))['watch_seconds__sum'] or 0
                watch_hours = round((total_seconds or 0) / 3600, 2)
    except Exception:
        # Be defensive: don't break profile rendering if any cross-app query fails
        user_posts = []
        posts_count = 0
        impressions = None
        watch_hours = None

    user_products = []
    user_jobs = []
    if Product:
        user_products = list(Product.objects.filter(
            Q(vendor_user=user) |
            Q(vendor_name__iexact=user.username) |
            Q(vendor_name__iexact=user.get_full_name())
        ).order_by('-impressions', '-last_synced')[:20])
    try:
        from languages.models import JobPost
        user_jobs = list(JobPost.objects.filter(
            Q(posted_by=user) |
            Q(recruiter_name__iexact=user.username) |
            Q(recruiter_name__iexact=user.get_full_name())
        ).order_by('-impressions', '-timestamp')[:20])
    except Exception:
        user_jobs = []

    analytics_items = [
        {'label': f'Post {post.id}', 'type': 'Post', 'impressions': post.impressions}
        for post in user_posts[:6]
    ]
    analytics_items.extend(
        {'label': product.name[:24], 'type': 'Product', 'impressions': product.impressions}
        for product in user_products[:6]
    )
    analytics_items.extend(
        {'label': job.post_content[:24], 'type': 'Job', 'impressions': job.impressions}
        for job in user_jobs[:6]
    )

    monthly_impressions = {}
    if FeedImpression:
        content_ids = {
            'post': [post.id for post in user_posts],
            'product': [product.id for product in user_products],
            'job': [job.id for job in user_jobs],
        }
        impression_events = FeedImpression.objects.filter(
            Q(content_type='post', object_id__in=content_ids['post']) |
            Q(content_type='product', object_id__in=content_ids['product']) |
            Q(content_type='job', object_id__in=content_ids['job'])
        )
        monthly_impressions = {
            row['month'].date(): row['total']
            for row in impression_events.annotate(month=TruncMonth('created_at')).values('month').annotate(
                total=Count('id')
            )
        }

    current_month = timezone.localdate().replace(day=1)
    months = []
    for offset in range(11, -1, -1):
        month_number = current_month.month - offset
        year = current_month.year + (month_number - 1) // 12
        month = ((month_number - 1) % 12) + 1
        month_date = date(year, month, 1)
        months.append({
            'label': month_date.strftime('%b %Y'),
            'impressions': monthly_impressions.get(month_date, 0),
        })

    graph_max = max(1, max(month['impressions'] for month in months))
    graph_points = []
    for index, month in enumerate(months):
        x = 10 if len(months) == 1 else 10 + (index * 180 / (len(months) - 1))
        y = 90 - (month['impressions'] / graph_max * 75)
        month['x'] = round(x, 2)
        month['y'] = round(y, 2)
        graph_points.append(f"{month['x']},{month['y']}")
    context = {
        'user': user, 'experiences': experiences, 'educations': educations,
        'skills': skills, 'social_connections': social_connections,
        'referral_link': referral_link, 'successful_referrals': successful_referrals,
        'total_referral_earnings': referral_earnings,
        'total_referral_count': successful_referrals.count() if Order else 0,
        'connections_count': connections_count,
        'followers_count': followers_count,
        'following_count': following_count,
        'user_posts': user_posts,
        'posts_count': posts_count,
        'impressions': impressions,
        'watch_hours': watch_hours,
        'likes_count': likes_count if 'likes_count' in locals() else 0,
        'job_ad_watch_count': job_ad_watch_count if 'job_ad_watch_count' in locals() else getattr(user, 'post_ad_watch_count', 0),
        'post_earnings_amount': post_earnings_amount if 'post_earnings_amount' in locals() else 0,
        'can_request_payout': can_request_payout if 'can_request_payout' in locals() else False,
        'pending_payout_request': pending_payout_request if 'pending_payout_request' in locals() else None,
        'user_products': user_products,
        'user_jobs': user_jobs,
        'analytics_items': analytics_items,
        'graph_points': ' '.join(graph_points),
        'graph_max': graph_max,
        'monthly_impressions': months,
    }
    try:
        return render(request, 'users/profile.html', context)
    except TemplateDoesNotExist:
        return render(request, 'profile.html', context)

@login_required
def profile_payout_request(request):
    if request.method != 'POST':
        return redirect('users:profile')

    user = request.user
    impressions = request.POST.get('impressions')
    likes_count = request.POST.get('likes_count')
    job_ad_watch_count = getattr(user, 'post_ad_watch_count', 0)
    qualifies_for_request = (
        (int(impressions or 0) >= 10000) and
        (int(likes_count or 0) >= 100) and
        job_ad_watch_count >= 100
    )
    if not qualifies_for_request:
        messages.error(request, 'You are not yet eligible to request a payout. Continue growing your posts.')
        return redirect('users:profile')

    card_type = request.POST.get('card_type', '').strip()
    card_number = request.POST.get('card_number', '').strip()
    bank_name = request.POST.get('bank_name', '').strip()

    if not card_type or not card_number:
        messages.error(request, 'Please select a card type and enter the last 4 digits of your card.')
        return redirect('users:profile')

    card_last4 = card_number[-4:] if len(card_number) >= 4 else card_number
    PayoutRequest.objects.create(
        user=user,
        amount=10.00,
        card_type=card_type,
        card_last4=card_last4,
        bank_name=bank_name if bank_name else None,
        status='pending',
    )
    messages.success(request, 'Your payout request has been submitted. We will process it shortly.')
    return redirect('users:profile')

@login_required
def profile_edit(request):
    user = request.user
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile was successfully updated!')
            return redirect('users:profile')
    else:
        form = ProfileEditForm(instance=user)
    try:
        return render(request, 'users/profile_edit.html', {'form': form})
    except TemplateDoesNotExist:
        return render(request, 'profile_edit.html', {'form': form})

@login_required
@csrf_exempt
def update_language(request):
    """Update user's preferred language"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            language = data.get('language', 'en')
            
            # Validate language code
            supported_languages = ['en', 'sw', 'lg', 'zu', 'xh', 'af', 'am', 'yo', 'ha', 'ar', 'fr', 'pt', 'es', 'de']
            if language not in supported_languages:
                language = 'en'
            
            request.user.language = language
            request.user.save()
            
            return JsonResponse({'success': True, 'language': language})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    return JsonResponse({'success': False, 'error': 'POST required'}, status=405)

# ==============================================================================
# AI CHAT LOGIC (Fixed for 2025 Standards)
# ==============================================================================

def _get_user_profile_data(user):
    """Retrieves detailed user context for personalization."""
    return {
        "full_name": user.get_full_name() or user.username, 
        "headline": getattr(user, 'headline', 'Professional'),
        "bio": getattr(user, 'about', 'No bio provided'),
        "skills": [skill.name for skill in Skill.objects.filter(user=user)],
        "experiences": [f"{exp.title} at {exp.company_name}" for exp in Experience.objects.filter(user=user)]
    }

def _format_history_for_sdk(messages):
    formatted = []
    for msg in messages:
        role = "model" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
        text = msg.get("text", "").strip()
        if not text:
            continue
        if formatted and formatted[-1]["role"] == role:
            formatted[-1]["parts"][0]["text"] += f"\n{text}"
        else:
            formatted.append({"role": role, "parts": [{"text": text}]})
    return formatted


def _extract_gemini_text(response):
    if not response:
        return ""

    text = getattr(response, "text", None)
    if text:
        return text

    parts = getattr(response, "parts", None)
    if parts:
        joined = "".join([getattr(p, "text", "") or "" for p in parts])
        if joined.strip():
            return joined

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if content is None:
            continue
        if getattr(content, "text", None):
            return content.text
        content_parts = getattr(content, "parts", None)
        if content_parts:
            joined = "".join([getattr(p, "text", "") or "" for p in content_parts])
            if joined.strip():
                return joined

    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, dict):
        if parsed.get("text"):
            return parsed.get("text")
        output = parsed.get("output") or {}
        if isinstance(output, dict) and output.get("text"):
            return output.get("text")

    return ""


@login_required
def profile_ai(request):
    try:
        return render(request, 'users/profile_ai.html', {'user': request.user})
    except TemplateDoesNotExist:
        return render(request, 'profile_ai.html', {'user': request.user})

@csrf_exempt
@login_required
def cerebras_proxy(request):
    """Proxies chat requests to Cerebras (primary) using gpt-oss-120b and falls back to Sunbird AI.
    Auto-detects language from user input. Supports business & job guidance across African languages.
    GUARANTEES: Always responds with clean, smart paragraphs. Never fails silently.
    """
    if request.method != 'POST':
        return JsonResponse({"error": "Only POST requests are allowed"}, status=405)

    try:
        body = json.loads(request.body)
        raw_contents = body.get('contents', []) or []
        user_language = body.get('language', 'en').lower()

        profile = _get_user_profile_data(request.user)

        lang_note_map = {
            'lg': ' Respond in Luganda when discussing with the user in Luganda.',
            'sw': ' Respond in Swahili when discussing with the user in Swahili.',
            'zu': ' Respond in Zulu when discussing with the user in Zulu.',
            'xh': ' Respond in Xhosa when discussing with the user in Xhosa.',
            'yo': ' Respond in Yoruba when discussing with the user in Yoruba.',
            'am': ' Respond in Amharic when discussing with the user in Amharic.',
            'ha': ' Respond in Hausa when discussing with the user in Hausa.',
        }
        lang_note = lang_note_map.get(user_language, '')

        default_instruction = f"""
You are Africana AI, an elite career advisor and business strategist for African professionals by Mwene Groups.

**USER PROFILE:**
Name: {profile['full_name']} | Role: {profile['headline']}
Skills: {', '.join(profile['skills'][:10]) or 'Not specified'}
Experience: {', '.join(profile['experiences'][:5]) if profile['experiences'] else 'Not specified'}

**YOUR CORE EXPERTISE:**

1. **JOB MARKET MASTERY**
   - Resume optimization for ATS & human readers
   - Cover letter strategies that convert interviews
   - Interview preparation: common questions, behavioral answers, salary negotiation
   - LinkedIn profile optimization & networking strategies
   - Job search tactics for African markets & international opportunities
   - Salary benchmarking for African tech, finance, and corporate sectors
   - Career progression roadmaps customized to user's profile

2. **BUSINESS & ENTREPRENEURSHIP**
   - Startup ideation validated against African market opportunities
   - Business plan development: market analysis, financial projections, go-to-market
   - Funding strategies: bootstrapping, angel investors, VC, government grants
   - Business model innovation for African contexts (mobile-first, offline-first)
   - Scaling strategies and operational excellence
   - Risk management and contingency planning

3. **PROFESSIONAL DEVELOPMENT**
   - Skill gap analysis based on user profile
   - Certification recommendations for career advancement
   - Online course suggestions (Coursera, Udemy, LinkedIn Learning)
   - Networking strategies for African professionals
   - Mentorship guidance and building professional relationships

4. **INDUSTRY INSIGHTS**
   - Tech: FinTech, AgriTech, EdTech, HealthTech trends in Africa
   - Finance: Banking, microfinance, investment opportunities
   - E-commerce: Cross-border selling, payment solutions
   - Manufacturing and logistics opportunities

**HOW YOU RESPOND:**
✅ Always answer in clear, polished paragraphs.
✅ Keep business and career guidance practical, actionable, and respectful.
✅ When asked to create documents, ONLY generate a PDF if the user explicitly requests it.
✅ Avoid making claims about your own availability or internal systems.
✅ If the user speaks in an African language, respond in that language using natural phrasing.
✅ When the user asks for resume, CV, business plan, or export, provide clear next-step advice first.
✅ Use professional tone for job search and startup strategy.
✅ Use bullet lists where it improves readability, but keep the message concise.

**LANGUAGE NOTE:**{lang_note}
"""
        system_instruction = body.get('system_instruction') or default_instruction

        messages = [{"role": "system", "content": system_instruction}]
        for msg in raw_contents[-10:]:
            role = "assistant" if msg.get("role", "").lower() in ["ai", "model", "assistant"] else "user"
            text = msg.get("text", "").strip()
            if text:
                messages.append({"role": role, "content": text})

        def try_cerebras():
            """Try Cerebras (primary) - excellent for business & job context"""
            api_key = os.environ.get("CEREBRAS_API_KEY", "").strip().replace('"', '').replace("'", "")
            if not api_key:
                return None, "Cerebras service unavailable"
            try:
                client = Cerebras(api_key=api_key)
                completion = client.chat.completions.create(
                    messages=messages,
                    model="gpt-oss-120b",
                    max_completion_tokens=2000,
                    temperature=0.7,
                    top_p=0.95,
                    stream=False,
                )
                response_text = completion.choices[0].message.content if completion.choices else ""
                if response_text and response_text.strip():
                    return response_text.strip(), None
                return None, "Cerebras service unavailable"
            except Exception as e:
                logging.warning("Cerebras request failed: %s", str(e), exc_info=True)
                return None, "Cerebras service unavailable"

        def try_sunbird():
            """Try Sunbird (fallback) - excellent for African languages"""
            sunbird_token = os.environ.get("SUNBIRD_API_KEY", "").strip().replace('"', '').replace("'", "")
            if not sunbird_token:
                return None, "Sunbird service unavailable"
            sunbird_url = "https://api.sunbird.ai/tasks/sunflower_inference"
            headers = {
                "accept": "application/json",
                "Authorization": f"Bearer {sunbird_token}",
                "Content-Type": "application/json",
            }
            payload = {"messages": messages}
            try:
                sunbird_response = requests.post(sunbird_url, headers=headers, json=payload, timeout=20)
                if sunbird_response.status_code == 200:
                    sunbird_data = sunbird_response.json()
                    response_text = ""
                    choices = sunbird_data.get("choices") or []
                    if choices:
                        response_text = choices[0].get("message", {}).get("content", "") or choices[0].get("content", "")
                    if not response_text:
                        response_text = sunbird_data.get("text") or sunbird_data.get("output_text") or sunbird_data.get("content") or ""
                    response_text = str(response_text).strip()
                    if response_text:
                        return response_text, None
                    logging.warning("Sunbird returned no usable content: %s", sunbird_data)
                    return None, "Sunbird service unavailable"
                logging.warning("Sunbird HTTP error %s: %s", sunbird_response.status_code, sunbird_response.text)
                return None, "Sunbird service unavailable"
            except requests.exceptions.RequestException as e:
                logging.warning("Sunbird request exception: %s", str(e), exc_info=True)
                return None, "Sunbird service unavailable"
            except Exception as e:
                logging.exception("Sunbird unexpected error")
                return None, "Sunbird service unavailable"

        response_text, error1 = try_cerebras()
        if response_text:
            return JsonResponse({
                "text": response_text,
                "model_used": "Cerebras gpt-oss-120b (Primary)",
                "language": user_language,
            })

        response_text, error2 = try_sunbird()
        if response_text:
            return JsonResponse({
                "text": response_text,
                "model_used": "Sunbird AI (Fallback)",
                "language": user_language,
            })

        fallback_response = f"""
**I'm experiencing temporary API issues, but here's your immediate guidance:**

Based on your profile ({profile['full_name']}, {profile['headline']}):

**Immediate Action Items:**
1. Update your professional presence with recent achievements and clear impact.
2. Sharpen your resume or business summary with metrics and local relevance.
3. Identify 2-3 job opportunities or market gaps you can pursue this week.
4. Focus on high-value skills and networking in your target industry.

I'll still provide a structured answer once the service is restored.
"""
        logging.warning(f"Both AI APIs failed. Cerebras: {error1}, Sunbird: {error2}. Using fallback.")
        return JsonResponse({
            "text": fallback_response,
            "model_used": "Fallback Response (APIs Temporarily Down)",
            "language": user_language,
        }, status=200)

    except json.JSONDecodeError as e:
        return JsonResponse({"error": f"Invalid request format: {str(e)}"}, status=400)
    except Exception as e:
        logging.error(f"Cerebras proxy error: {str(e)}", exc_info=True)
        return JsonResponse({
            "text": "I'm experiencing a technical issue. Please try again in a moment. Your question is important!",
            "model_used": "Error Recovery",
        }, status=200)
ai_quiz_generator = profile_ai


@csrf_exempt
@login_required
def generate_advert_image(request):
    """Generates an advertisement graphic using Sunbird AI's Image Generation API."""
    if request.method != 'POST':
        return JsonResponse({"error": "POST only"}, status=405)

    sunbird_token = os.environ.get("SUNBIRD_API_KEY", "").strip().replace('"', '').replace("'", "")
    if not sunbird_token:
        return JsonResponse({"error": "Sunbird API key configuration missing."}, status=500)

    try:
        data = json.loads(request.body)
        user_prompt = data.get('prompt', '').strip()

        if not user_prompt:
            return JsonResponse({"error": "Please provide a description for the advertisement image."}, status=400)

        # Optimize prompt styling automatically for sleek African e-commerce/tech products
        enhanced_prompt = (
            f"Professional product marketing commercial photograph, studio lighting, crisp clean focus, "
            f"vibrant modern aesthetic, tailored for an African digital business landscape: {user_prompt}"
        )

        # Target Sunbird's text-to-image pipeline
        sunbird_url = "https://api.sunbird.ai/tasks/text_to_image"
        headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {sunbird_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "prompt": enhanced_prompt
        }

        try:
            response = requests.post(sunbird_url, headers=headers, json=payload, timeout=30)
        except requests.exceptions.RequestException as req_err:
            logging.exception("Sunbird request failed")
            user_msg = "Unable to contact the image generation service right now. Please try again later."
            details = str(req_err)
            payload = {'error': 'Network error', 'user_error': user_msg}
            if settings.DEBUG:
                payload['details'] = details
            return JsonResponse(payload, status=502)

        # If Sunbird rejects the HTTP method, try a commonly used alternate path
        if response.status_code == 405:
            alt_url = "https://api.sunbird.ai/tasks/text-to-image"
            logging.info("Sunbird returned 405; retrying with alternate endpoint %s", alt_url)
            try:
                alt_resp = requests.post(alt_url, headers=headers, json=payload, timeout=30)
                response = alt_resp
            except requests.exceptions.RequestException as alt_err:
                logging.exception("Sunbird alternate endpoint request failed")
                user_msg = "Image service appears misconfigured. Please try again later."
                payload = {'error': 'Network error', 'user_error': user_msg}
                if settings.DEBUG:
                    payload['details'] = str(alt_err)
                return JsonResponse(payload, status=502)

        # Parse response and provide user-friendly error messages
        if response.status_code == 200:
            response_data = response.json()
            # Sunbird provides a hosted URL or a base64 string depending on their task configuration. 
            # If they return a direct image URL under 'image_url' or 'url':
            image_url = response_data.get("image_url") or response_data.get("url")
            
            # Fallback check if it returns raw base64 data instead
            if not image_url and "base64" in response_data:
                image_url = f"data:image/jpeg;base64,{response_data['base64']}"

            if image_url:
                return JsonResponse({
                    "success": True,
                    "image_url": image_url,
                    "prompt_used": user_prompt
                })
            
            logging.warning("Sunbird returned 200 but no image data: %s", response.text)
            user_msg = "Image service processed your request but did not return a usable image. Try simplifying the description."
            payload = {'error': 'No image returned', 'user_error': user_msg}
            if settings.DEBUG:
                payload['details'] = response.text
            return JsonResponse(payload, status=502)
        else:
            # Map common HTTP errors to friendly messages
            raw_text = (response.text or '').strip()
            if response.status_code == 400:
                user_msg = "Couldn't understand the image request. Try a shorter, simpler description."
            elif response.status_code == 401 or response.status_code == 403:
                user_msg = "Authorization failed for image generation. Site configuration may be missing or invalid."
            elif response.status_code == 405:
                user_msg = "Image generation is not enabled on this server. Please try a different request or contact support."
            elif response.status_code == 429:
                user_msg = "Image service is busy (rate limit). Please wait a moment and try again."
            elif 500 <= response.status_code < 600:
                user_msg = "Image service is temporarily unavailable. Please try again later."
            else:
                user_msg = "Image generation failed. Please try again or simplify your prompt."

            logging.error("Sunbird Image API error %s: %s", response.status_code, raw_text)
            payload = {'error': f'Sunbird Image API error', 'user_error': user_msg}
            if settings.DEBUG:
                payload['details'] = raw_text
            return JsonResponse(payload, status=response.status_code)

    except Exception as e:
        logging.error(f"Sunbird Image Generation Exception: {str(e)}", exc_info=True)
        return JsonResponse({"error": f"Internal image pipeline error: {str(e)}"}, status=500)



@csrf_exempt
@login_required
def generate_document_pdf(request):
    """
    Accepts text markdown or raw data from Africana AI, transforms it into an 
    excellently styled document structure, and renders it directly into a PDF download.
    """
    if request.method == 'POST':
        # Step A: Capture data from the AI chat session
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid request content format."}, status=400)
            
        text_content = data.get('text', '').strip()
        doc_type = data.get('doc_type', 'document') # 'resume' or 'business_plan'
        
        if not text_content:
            return JsonResponse({"error": "No document data provided to compile."}, status=400)
            
        # Temporarily cache data in the user's session to allow immediate safe retrieval via GET download
        request.session['pending_pdf_text'] = text_content
        request.session['pending_pdf_type'] = doc_type
        
        # Return link routing target
        return JsonResponse({
            "success": True, 
            "redirect_url": reverse('users:generate_document_pdf')
        })

    # Step B: When the download route is requested via a GET request
    text_content = request.session.get('pending_pdf_text', '')
    doc_type = request.session.get('pending_pdf_type', 'document')

    if not text_content:
        return redirect('users:profile_ai')

    # If the user clicks the final download action link
    if request.GET.get('download') == '1':
        # Convert plain line-breaks to printable semantic elements safely
        formatted_html_content = text_content.replace('\n', '<br>').replace('**', '<b>').replace('</b><b>', '')

        # Apply strict professional CSS design guidelines tailored strictly for paper margins
        accent_color = "#16a34a" if doc_type == "resume" else "#0f172a" # Green for resumes, deep corporate blue for plans

        html_string = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                    color: #1e293b;
                    line-height: 1.6;
                    font-size: 10.5pt;
                    margin: 0;
                    padding: 20mm 15mm;
                }}
                h1 {{ color: {accent_color}; }}
                .content-wrapper {{ max-width: 800px; margin: 0 auto; }}
            </style>
        </head>
        <body>
            <div class="content-wrapper">
                {formatted_html_content}
            </div>
        </body>
        </html>
        """

        # Use Playwright (Chromium) to render HTML to PDF for robust cloud builds
        try:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError as import_error:
                logging.error('Playwright is not installed for PDF rendering: %s', import_error)
                return HttpResponse(
                    'PDF rendering is unavailable on this server. Please install playwright and its runtime dependencies.',
                    status=503
                )

            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page()
                page.set_content(html_string, wait_until='networkidle')
                pdf_bytes = page.pdf(format='A4', margin={'top':'20mm','bottom':'20mm','left':'15mm','right':'15mm'})
                browser.close()

            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="africana_{doc_type}_{int(time.time())}.pdf"'

            # Clean up session space safely after download
            del request.session['pending_pdf_text']
            del request.session['pending_pdf_type']

            return response
        except Exception as e:
            logging.error(f"Playwright PDF generation failed: {str(e)}", exc_info=True)
            return HttpResponse("PDF rendering failed on server.", status=500)

    # Render intermediate loading display before auto-download execution sets up
    return render(request, 'users/download_pdf.html', {'doc_type': doc_type})
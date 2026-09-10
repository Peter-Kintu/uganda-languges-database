import os
import json
import logging
import requests
import time
import base64
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta, date
from django.template.loader import render_to_string
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib import messages
from django.core.mail import send_mail
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib.auth.forms import AuthenticationForm
from django.urls import reverse
from django.db import IntegrityError, models, transaction
from django.db.models import Q, Count
from django.db.models.functions import TruncMonth
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template import TemplateDoesNotExist
from .models import EventBooking
import uuid
from io import BytesIO
from pathlib import Path
import qrcode
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

logger = logging.getLogger(__name__)


staff_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='/admin/login/',
)


@staff_required
def registration_admin(request):
    bookings = EventBooking.objects.all()
    ticket_type = request.GET.get('ticket_type', '').strip().upper()
    status = request.GET.get('status', '').strip().lower()
    if ticket_type in {'FREE', 'CEO'}:
        bookings = bookings.filter(ticket_type=ticket_type)
    if status == 'pending':
        bookings = bookings.filter(is_verified=False)
    elif status == 'verified':
        bookings = bookings.filter(is_verified=True)
    return render(request, 'registration_admin.html', {
        'bookings': bookings,
        'selected_ticket_type': ticket_type,
        'selected_status': status,
        'total_count': EventBooking.objects.count(),
        'pending_count': EventBooking.objects.filter(is_verified=False).count(),
        'verified_count': EventBooking.objects.filter(is_verified=True).count(),
    })


@staff_required
def verify_registration(request, booking_ref):
    if request.method != 'POST':
        return redirect('registration_admin')
    booking = get_object_or_404(EventBooking, booking_ref=booking_ref)
    booking.is_verified = True
    if booking.ticket_type == 'CEO' and booking.founding_member_number is None:
        last_number = EventBooking.objects.filter(
            ticket_type='CEO',
            founding_member_number__isnull=False,
        ).order_by('-founding_member_number').values_list('founding_member_number', flat=True).first() or 0
        if last_number >= 300:
            messages.error(request, 'All 300 founding CEO member cards have already been assigned.')
            return redirect('registration_admin')
        booking.founding_member_number = last_number + 1
    booking.save(update_fields=['is_verified', 'founding_member_number'])
    messages.success(request, f'{booking.full_name} has been marked as verified.')
    return redirect('registration_admin')


@staff_required
def delete_registration(request, booking_ref):
    if request.method != 'POST':
        return redirect('registration_admin')
    booking = get_object_or_404(EventBooking, booking_ref=booking_ref)
    attendee_name = booking.full_name
    if booking.payment_proof:
        booking.payment_proof.delete(save=False)
    booking.delete()
    messages.success(request, f'{attendee_name} has been removed from the registrations.')
    return redirect('registration_admin')


def launch_registration(request):
    if request.method == 'POST':
        ticket_type = request.POST.get('ticket_type', 'FREE')
        if ticket_type not in {'FREE', 'CEO'}:
            messages.error(request, 'Please select a valid ticket category.')
            return render(request, 'launch_registration.html')

        transaction_id = request.POST.get('transaction_id', '').strip()
        payment_proof = request.FILES.get('payment_proof')
        if ticket_type == 'CEO' and not transaction_id and not payment_proof:
            messages.error(request, 'CEO Table bookings need a MoMo reference or payment proof.')
            return render(request, 'launch_registration.html')

        full_name = request.POST.get('full_name', '').strip()
        if EventBooking.objects.filter(full_name__iexact=full_name).exists():
            messages.error(request, 'This name has already been registered. Each attendee name can register only once.')
            return render(request, 'launch_registration.html')

        booking = EventBooking.objects.create(
            booking_ref=f"BOOK-{uuid.uuid4().hex[:8].upper()}",
            full_name=full_name,
            phone=request.POST.get('phone', '').strip(),
            email=request.POST.get('email', '').strip(),
            ticket_type=ticket_type,
            transaction_id=transaction_id,
            payment_proof=payment_proof,
            is_verified=ticket_type == 'FREE',
        )
        return redirect('registration_status', booking_ref=booking.booking_ref)

    return render(request, 'launch_registration.html')


def registration_status(request, booking_ref):
    booking = get_object_or_404(EventBooking, booking_ref=booking_ref)
    status_url = request.build_absolute_uri()
    share_message = (
        f"Africana AI Festival registration for {booking.full_name}: "
        f"{booking.get_ticket_type_display()} - booking reference {booking.booking_ref}. "
        f"Check confirmation: {status_url}"
    )
    return render(request, 'registration_status.html', {
        'booking': booking,
        'share_message': share_message,
        'status_url': status_url,
    })


def download_registration(request, booking_ref):
    booking = get_object_or_404(EventBooking, booking_ref=booking_ref)
    status = 'Verified' if booking.is_verified else 'Awaiting manual payment verification'
    receipt = '\n'.join([
        'AFRICANA AI FESTIVAL REGISTRATION',
        '================================',
        f'Name: {booking.full_name}',
        f'Phone: {booking.phone}',
        f'Email: {booking.email}',
        f'Ticket: {booking.get_ticket_type_display()}',
        f'Booking reference: {booking.booking_ref}',
        f'Status: {status}',
        f'Registered: {booking.created_at:%d %B %Y %H:%M}',
        '',
        'Keep this receipt for event check-in.',
    ])
    response = HttpResponse(receipt, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{booking.booking_ref}-registration.txt"'
    return response


def _card_font(size, bold=False):
    font_name = 'LiberationSans-Bold.ttf' if bold else 'LiberationSans-Regular.ttf'
    for font_dir in ('/usr/share/fonts/truetype/liberation2', '/usr/share/fonts/truetype/dejavu'):
        font_path = Path(font_dir) / font_name
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)
    return ImageFont.load_default()


def download_ceo_card(request, booking_ref):
    booking = get_object_or_404(EventBooking, booking_ref=booking_ref)
    if booking.ticket_type != 'CEO' or not booking.is_verified or booking.founding_member_number is None:
        return HttpResponse('CEO card is available after payment verification.', status=404)

    image_path = Path(settings.BASE_DIR) / 'static' / 'images' / 'africanaai_card.png'
    card = Image.open(image_path).convert('RGB')
    draw = ImageDraw.Draw(card)
    member_label = f'{booking.founding_member_number:03d}/300'
    verify_url = request.build_absolute_uri(reverse('verify_delegate', args=[booking.booking_ref]))

    # Cover the sample identity fields on the supplied artwork with this booking's data.
    draw.rectangle((370, 270, 1530, 335), fill=(18, 18, 18))
    draw.text((960, 285), f'FOUNDING MEMBER {member_label}  |  {booking.full_name.upper()}',
              fill=(255, 220, 145), font=_card_font(34, bold=True), anchor='mm')
    draw.rectangle((600, 1070, 1190, 1135), fill=(18, 18, 18))
    draw.text((895, 1102), f'{booking.booking_ref}  |  {booking.full_name}',
              fill=(255, 220, 145), font=_card_font(25, bold=True), anchor='mm')

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=10, border=2)
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color='#17130d', back_color='#f8df9a').convert('RGB').resize((260, 260))
    card.paste(qr_image, (1460, 840))

    output = BytesIO()
    card.save(output, format='PNG', optimize=True)
    response = HttpResponse(output.getvalue(), content_type='image/png')
    response['Content-Disposition'] = f'attachment; filename="{booking.booking_ref}-ceo-card.png"'
    return response


def verify_delegate(request, booking_no):
    booking = EventBooking.objects.filter(
        booking_ref=booking_no.upper(), ticket_type='CEO', is_verified=True
    ).first()
    return render(request, 'verify.html', {'booking': booking, 'booking_no': booking_no.upper()})


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


def _send_welcome_email(user):
    if not user.email:
        return
    try:
        send_mail(
            subject='Welcome to Africana AI',
            message=(
                f'Hi {user.get_full_name() or user.username},\n\n'
                'Thank you for signing up for Africana AI. Your account is ready.\n\n'
                'Visit https://www.africanaai.info to get started.\n\n'
                'The Africana AI team'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Welcome email could not be sent to %s.', user.email)

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
    text = request.GET.get('text', '').strip()
    lang = request.GET.get('lang', 'en').lower().strip()
    if not text:
        return HttpResponse("No text provided", status=400)

    if len(text) > 2000:
        return HttpResponse("Text too long", status=400)

    tts_language_map = {
        'lug': 'lg', 'nyn': 'en', 'ach': 'en', 'lgg': 'en', 'teo': 'en',
        'xog': 'en', 'nyo': 'en', 'alz': 'en', 'swa': 'sw', 'kin': 'rw',
    }
    lang = tts_language_map.get(lang, lang)
    
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
            _send_welcome_email(user)

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
                _send_welcome_email(user)
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
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required.'}, status=405)

    tracking_id = request.POST.get('OrderTrackingId') or request.POST.get('order_tracking_id')
    if not tracking_id:
        return JsonResponse({'status': 'error', 'message': 'Missing tracking id.'}, status=400)

    payment = get_object_or_404(PesapalPayment.objects.select_related('subscription'), tracking_id=tracking_id)

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

    provider_tracking_id = transaction_payload.get('orderTrackingId') or transaction_payload.get('OrderTrackingId')
    if provider_tracking_id and str(provider_tracking_id) != str(payment.tracking_id):
        return JsonResponse({'status': 'error', 'message': 'Payment tracking mismatch.'}, status=400)

    provider_reference = (
        transaction_payload.get('merchantReference')
        or transaction_payload.get('merchant_reference')
        or transaction_payload.get('id')
        or transaction_payload.get('order_id')
    )
    if provider_reference and str(provider_reference) != str(payment.order_id):
        return JsonResponse({'status': 'error', 'message': 'Payment order mismatch.'}, status=400)

    try:
        provider_amount = Decimal(str(transaction_payload.get('amount')))
    except (TypeError, ValueError, InvalidOperation):
        return JsonResponse({'status': 'error', 'message': 'Payment amount missing or invalid.'}, status=400)
    provider_currency = str(transaction_payload.get('currency') or '').upper()
    if provider_amount != payment.amount or provider_currency != payment.currency.upper():
        return JsonResponse({'status': 'error', 'message': 'Payment amount or currency mismatch.'}, status=400)

    status = str(transaction_payload.get('status') or transaction_payload.get('Status') or '').upper()
    with transaction.atomic():
        locked_payment = PesapalPayment.objects.select_for_update().select_related('subscription').get(pk=payment.pk)
        if locked_payment.status == 'PAID':
            return JsonResponse({'status': 'OK', 'message': 'Payment notification already processed.'})
        if locked_payment.status in {'FAILED', 'CANCELLED'}:
            return JsonResponse({'status': 'OK', 'message': 'Payment is already in a terminal state.'})
        if status in {'COMPLETED', 'PAID', 'SUCCESS', 'SUCCESSFUL'}:
            if not locked_payment.subscription:
                return JsonResponse({'status': 'error', 'message': 'Payment has no subscription.'}, status=409)
            now = timezone.now()
            locked_payment.status = 'PAID'
            locked_payment.subscription.status = 'active'
            locked_payment.subscription.is_active = True
            locked_payment.subscription.start_date = now
            locked_payment.subscription.end_date = now + timedelta(days=30)
            locked_payment.subscription.save(update_fields=['status', 'is_active', 'start_date', 'end_date'])
        elif status in {'FAILED', 'CANCELLED', 'CANCELED'}:
            locked_payment.status = 'CANCELLED' if status in {'CANCELLED', 'CANCELED'} else 'FAILED'
            if locked_payment.subscription:
                locked_payment.subscription.status = 'failed'
                locked_payment.subscription.is_active = False
                locked_payment.subscription.save(update_fields=['status', 'is_active'])
        else:
            return JsonResponse({'status': 'OK', 'message': 'Payment remains pending.'})
        locked_payment.save(update_fields=['status', 'updated_at'])

    return JsonResponse({'status': 'OK', 'message': 'Pesapal notification processed.'})


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

@login_required
def analyze_ai_attachment(request):
    """Analyze a user-provided image or text document against their selected goal."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    attachment = request.FILES.get('attachment')
    if not attachment:
        return JsonResponse({'error': 'Please choose a file to analyze.'}, status=400)
    if attachment.size > 8 * 1024 * 1024:
        return JsonResponse({'error': 'Files must be 8 MB or smaller.'}, status=400)

    allowed_types = {
        'image/jpeg', 'image/png', 'image/webp', 'application/pdf',
        'text/plain', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    if attachment.content_type not in allowed_types:
        return JsonResponse({'error': 'Upload a JPG, PNG, WEBP, PDF, DOCX, or TXT file.'}, status=400)

    focus_labels = {
        'career': 'career growth and professional direction',
        'jobs': 'finding realistic job opportunities and improving applications',
        'business': 'building and validating a practical African business',
        'skills': 'learning priorities and closing skill gaps',
    }
    focus = focus_labels.get(request.POST.get('user_focus', 'career').lower(), focus_labels['career'])
    user_need = request.POST.get('user_need', '').strip()[:1000]
    language = request.POST.get('language', 'en').lower()
    profile = _get_user_profile_data(request.user)
    profile_note = (
        f"User profile: {profile['full_name']}; role: {profile['headline']}; "
        f"skills: {', '.join(profile['skills'][:10]) or 'not specified'}; "
        f"experience: {', '.join(profile['experiences'][:5]) or 'not specified'}."
    )
    instruction = (
        f"You are Africana AI, a practical African career and business companion. {profile_note} "
        f"The user's current focus is {focus}. Their specific request is: {user_need or 'Give the most useful feedback for this file.'} "
        "Analyze only what is present. Give concise, specific feedback, explain why it matters, "
        "and finish with three prioritized next actions. For clothing images, comment only on outfit "
        "coordination, fit, color, grooming presentation, context, and culturally respectful styling; "
        "do not infer identity, body judgments, health, age, or protected traits. "
        f"Respond in {language} when it is a supported language; otherwise respond in clear English."
    )

    try:
        if attachment.content_type.startswith('image/'):
            api_key = os.environ.get('GEMINI_API_KEY', '').strip().replace('"', '').replace("'", '')
            if not api_key:
                return JsonResponse({'error': 'Image analysis is not configured yet.'}, status=503)
            vision_model = getattr(settings, 'GEMINI_VISION_MODEL', 'gemini-2.5-flash')
            encoded = base64.b64encode(attachment.read()).decode('ascii')
            payload = {
                'contents': [{'parts': [
                    {'text': instruction},
                    {'inline_data': {'mime_type': attachment.content_type, 'data': encoded}},
                ]}],
                'generationConfig': {'temperature': 0.45, 'maxOutputTokens': 1200},
            }
            response = requests.post(
                f'https://generativelanguage.googleapis.com/v1beta/models/{vision_model}:generateContent',
                params={'key': api_key}, json=payload, timeout=35,
            )
            response.raise_for_status()
            candidates = response.json().get('candidates', [])
            parts = candidates[0].get('content', {}).get('parts', []) if candidates else []
            result = ''.join(part.get('text', '') for part in parts).strip()
        else:
            if attachment.content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                with zipfile.ZipFile(attachment) as document_zip:
                    document_xml = document_zip.read('word/document.xml')
                root = ET.fromstring(document_xml)
                raw_text = ' '.join(node.text or '' for node in root.iter() if node.tag.endswith('}t'))
            else:
                raw_text = attachment.read().decode('utf-8', errors='ignore')
            if attachment.content_type == 'application/pdf':
                return JsonResponse({'error': 'PDF text extraction is not available yet. Upload a DOCX or TXT copy.'}, status=400)
            document_messages = [
                {'role': 'system', 'content': instruction},
                {'role': 'user', 'content': raw_text[:24000]},
            ]
            result = None
            api_key = os.environ.get('CEREBRAS_API_KEY', '').strip().replace('"', '').replace("'", '')
            if api_key:
                try:
                    client = Cerebras(api_key=api_key)
                    completion = client.chat.completions.create(
                        messages=document_messages, model='gpt-oss-120b',
                        max_completion_tokens=1200, temperature=0.45, stream=False,
                    )
                    result = completion.choices[0].message.content.strip() if completion.choices else ''
                except Exception as error:
                    logging.warning('Cerebras document analysis failed: %s', str(error)[:200])
            if not result:
                sunbird_token = os.environ.get('SUNBIRD_API_KEY', '').strip().replace('"', '').replace("'", '')
                if sunbird_token:
                    sunbird_response = requests.post(
                        'https://api.sunbird.ai/tasks/sunflower_inference',
                        headers={
                            'accept': 'application/json',
                            'Authorization': f'Bearer {sunbird_token}',
                            'Content-Type': 'application/json',
                        },
                        json={'messages': document_messages}, timeout=25,
                    )
                    sunbird_response.raise_for_status()
                    sunbird_data = sunbird_response.json()
                    choices = sunbird_data.get('choices') or []
                    if choices:
                        result = choices[0].get('message', {}).get('content', '') or choices[0].get('content', '')
                    result = result or sunbird_data.get('text') or sunbird_data.get('output_text') or sunbird_data.get('content') or ''
                    result = str(result).strip()

        if not result:
            return JsonResponse({'error': 'The AI could not produce feedback for this file.'}, status=502)
        return JsonResponse({'text': result, 'filename': attachment.name})
    except (requests.RequestException, UnicodeDecodeError, ValueError) as error:
        logging.warning('Attachment analysis failed: %s', str(error)[:200])
        return JsonResponse({'error': 'Attachment analysis is temporarily unavailable.'}, status=502)
    except Exception as error:
        logging.warning('Attachment analysis error: %s', str(error)[:200])
        return JsonResponse({'error': 'Attachment analysis is temporarily unavailable.'}, status=502)


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
        user_focus = body.get('user_focus', 'career').lower()
        focus_labels = {
            'career': 'career growth and professional direction',
            'jobs': 'finding realistic job opportunities and building an application pipeline',
            'business': 'building and validating a practical African business',
            'skills': 'targeted learning and closing the user\'s skill gaps',
        }
        focus_instruction = focus_labels.get(user_focus, focus_labels['career'])

        if not isinstance(raw_contents, list) or len(raw_contents) > 30:
            return JsonResponse({'error': 'Conversation history is too large.'}, status=400)
        if sum(len(str(item)) for item in raw_contents) > 30000:
            return JsonResponse({'error': 'Conversation content is too large.'}, status=400)

        profile = _get_user_profile_data(request.user)

        lang_note_map = {
            'lg': ' Respond in Luganda when discussing with the user in Luganda.',
            'lug': ' Respond in Luganda when discussing with the user in Luganda.',
            'nyn': ' Respond in Runyankole when discussing with the user in Runyankole.',
            'ach': ' Respond in Acholi when discussing with the user in Acholi.',
            'lgg': ' Respond in Lugbara when discussing with the user in Lugbara.',
            'teo': ' Respond in Ateso when discussing with the user in Ateso.',
            'xog': ' Respond in Lusoga when discussing with the user in Lusoga.',
            'nyo': ' Respond in Runyoro when discussing with the user in Runyoro.',
            'alz': ' Respond in Alur when discussing with the user in Alur.',
            'sw': ' Respond in Swahili when discussing with the user in Swahili.',
            'swa': ' Respond in Swahili when discussing with the user in Swahili.',
            'rw': ' Respond in Kinyarwanda when discussing with the user in Kinyarwanda.',
            'kin': ' Respond in Kinyarwanda when discussing with the user in Kinyarwanda.',
            'zu': ' Respond in Zulu when discussing with the user in Zulu.',
            'xh': ' Respond in Xhosa when discussing with the user in Xhosa.',
            'yo': ' Respond in Yoruba when discussing with the user in Yoruba.',
            'am': ' Respond in Amharic when discussing with the user in Amharic.',
            'ha': ' Respond in Hausa when discussing with the user in Hausa.',
            'ig': ' Respond in Igbo when discussing with the user in Igbo.',
            'sn': ' Respond in Shona when discussing with the user in Shona.',
            'so': ' Respond in Somali when discussing with the user in Somali.',
            'om': ' Respond in Oromo when discussing with the user in Oromo.',
            'ti': ' Respond in Tigrinya when discussing with the user in Tigrinya.',
            'ln': ' Respond in Lingala when discussing with the user in Lingala.',
            'mg': ' Respond in Malagasy when discussing with the user in Malagasy.',
            'st': ' Respond in Sesotho when discussing with the user in Sesotho.',
            'tn': ' Respond in Setswana when discussing with the user in Setswana.',
            'ee': ' Respond in Ewe when discussing with the user in Ewe.',
            'ak': ' Respond in Akan when discussing with the user in Akan.',
            'wo': ' Respond in Wolof when discussing with the user in Wolof.',
            'ff': ' Respond in Fulfulde when discussing with the user in Fulfulde.',
            'bm': ' Respond in Bambara when discussing with the user in Bambara.',
            'ber': ' Respond in Tamazight when discussing with the user in Tamazight.',
            'ttj': ' Respond in Rutooro when discussing with the user in Rutooro.',
            'cgg': ' Respond in Rukiga when discussing with the user in Rukiga.',
            'myx': ' Respond in Lumasaba when discussing with the user in Lumasaba.',
            'kpz': ' Respond in Kupsapiiny when discussing with the user in Kupsapiiny.',
            'pok': ' Respond in Pokot when discussing with the user in Pokot.',
        }
        lang_note = lang_note_map.get(user_language, '')

        default_instruction = f"""
You are Africana AI, an elite career advisor and business strategist for African professionals by Mwene Groups.

**USER PROFILE:**
Name: {profile['full_name']} | Role: {profile['headline']}
Skills: {', '.join(profile['skills'][:10]) or 'Not specified'}
Experience: {', '.join(profile['experiences'][:5]) if profile['experiences'] else 'Not specified'}

**CURRENT USER FOCUS:**
Prioritize {focus_instruction}. Connect every recommendation to the user's profile and end with one clear next action.

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
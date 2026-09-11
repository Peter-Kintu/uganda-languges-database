from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.serializers import serialize
from django.db.models import F, Sum, Max, Q, Count
from django.db.models.functions import TruncMonth
from django.db.models.deletion import ProtectedError
from decimal import Decimal, InvalidOperation # Import InvalidOperation for robust number handling
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password, make_password
from django.views.decorators.csrf import csrf_exempt
from .forms import ProductForm, NegotiationForm 
from .models import (
    Product, Cart, CartItem, CommercePayment, InventoryItem, StockMovement, PromotionCampaign,
    AffiliateEvent, AffiliatePayout, LiveShoppingSession, LivePinnedProduct,
)
from django.utils import timezone
from datetime import date, timedelta
import re 
import os
import json
import uuid
import secrets
import requests
import qrcode
from io import BytesIO
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import Order, OrderItem
from users.models import Notification
from aliexpress_api import AliexpressApi, models
from django.conf import settings
import logging
from django.utils.text import slugify

User = get_user_model()


def _agent_reply(language, message, products=None, order=None):
    if order:
        labels = {'en': 'Order', 'lg': 'Oda', 'sw': 'Agizo', 'ha': 'Oda'}
        return f"{labels.get(language, 'Order')} #{order.id}: {order.get_status_display()}."
    if products:
        names = ', '.join(product.name for product in products[:5])
        return f"{names}."
    prompts = {
        'lg': 'Nnyamba okunoonya ekintu oba okulondoola oda yo.',
        'sw': 'Naweza kutafuta bidhaa au kufuatilia agizo lako.',
        'ha': 'Zan iya nemo kaya ko bin diddigin odarka.',
    }
    return prompts.get(language, 'Tell me what product you need or share an order number.')


@login_required
def commerce_agent(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    payload = request.POST if request.POST else json.loads(request.body or '{}')
    message = str(payload.get('message', '')).strip()
    language = str(payload.get('language') or getattr(request.user, 'language', 'en')).lower()
    if not message:
        return JsonResponse({'error': 'message is required.'}, status=400)

    order_match = re.search(r'(?:order|oda|agizo)\s*#?([0-9]+)', message, re.IGNORECASE)
    if order_match:
        order = Order.objects.filter(id=order_match.group(1), buyer=request.user).first()
        if not order:
            return JsonResponse({'reply': 'Order not found.' if language == 'en' else _agent_reply(language, message)})
        return JsonResponse({'reply': _agent_reply(language, message, order=order), 'order_id': order.id, 'status': order.status})

    query = re.sub(r'\b(find|search|show|look for|nnyamba|noonya|tafuta|nemo)\b', '', message, flags=re.IGNORECASE).strip()
    products = list(Product.objects.filter(name__icontains=query).order_by('-impressions')[:5]) if query else []
    return JsonResponse({'reply': _agent_reply(language, message, products=products), 'products': [{'id': p.id, 'name': p.name, 'price': str(p.price), 'currency': p.get_currency_code()} for p in products]})


@login_required
def merchant_inventory(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'GET required.'}, status=405)
    items = InventoryItem.objects.filter(product__vendor_user=request.user).select_related('product')
    return JsonResponse({'items': [{'product_id': item.product_id, 'name': item.product.name, 'sku': item.sku, 'on_hand': item.quantity_on_hand, 'reserved': item.quantity_reserved, 'available': item.available_quantity, 'version': item.version} for item in items]})


@login_required
def merchant_inventory_sync(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    product_id = payload.get('product_id')
    quantity = payload.get('quantity')
    idempotency_key = str(payload.get('idempotency_key', '')).strip()
    if not product_id or not isinstance(quantity, int) or not idempotency_key:
        return JsonResponse({'error': 'product_id, integer quantity, and idempotency_key are required.'}, status=400)
    product = get_object_or_404(Product, id=product_id, vendor_user=request.user)
    with transaction.atomic():
        item, _ = InventoryItem.objects.select_for_update().get_or_create(product=product, defaults={'sku': f'SKU-{product.id}'})
        if StockMovement.objects.filter(reference=idempotency_key).exists():
            return JsonResponse({'status': 'already_applied', 'version': item.version})
        if item.quantity_on_hand + quantity < item.quantity_reserved:
            return JsonResponse({'error': 'Quantity cannot be below reserved stock.'}, status=409)
        item.quantity_on_hand += quantity
        item.version += 1
        item.save(update_fields=['quantity_on_hand', 'version', 'updated_at'])
        StockMovement.objects.create(inventory=item, movement_type='restock' if quantity >= 0 else 'adjustment', quantity=quantity, reference=idempotency_key)
    return JsonResponse({'status': 'applied', 'product_id': product.id, 'on_hand': item.quantity_on_hand, 'version': item.version})


@login_required
def start_commerce_payment(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    cart = get_user_cart(request)
    if not cart.items.exists():
        return JsonResponse({'error': 'Cart is empty.'}, status=400)
    delivery = request.session.get('delivery_details', {})
    if not all(delivery.get(field) for field in ('address', 'city', 'phone')):
        return JsonResponse({'error': 'Please provide delivery details before payment.'}, status=400)
    first_item = cart.items.select_related('product').first()
    with transaction.atomic():
        delivery_pin = f'{secrets.randbelow(1000000):06d}'
        order = Order.objects.create(
            buyer=request.user, total_amount=cart.cart_total, currency=first_item.product.get_currency_code(),
            status='payment_pending', delivery_address=delivery.get('address', ''), delivery_city=delivery.get('city', ''),
            delivery_phone=delivery.get('phone', ''), delivery_latitude=delivery.get('latitude') or None, delivery_longitude=delivery.get('longitude') or None,
            delivery_pin_hash=make_password(delivery_pin),
        )
        for item in cart.items.select_related('product'):
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity, price_at_purchase=item.product.negotiated_price or item.product.price, commission_at_purchase=item.product.referral_commission)
        payment = CommercePayment.objects.create(order=order, pesapal_order_id=f'eshop-{order.id}-{uuid.uuid4().hex[:8]}', amount=order.total_amount, currency=order.currency)
    try:
        from users.views import _pesapal_notification_id, _pesapal_request
        callback_url = request.build_absolute_uri(reverse('eshop:payment_callback'))
        notification_url = request.build_absolute_uri(reverse('pesapal_ipn'))
        token = _pesapal_request('post', 'Auth/RequestToken').get('token')
        notification_id = _pesapal_notification_id(notification_url, token)
        response = _pesapal_request('post', 'Transactions/SubmitOrderRequest', json_data={'id': payment.pesapal_order_id, 'currency': payment.currency, 'amount': f'{payment.amount:.2f}', 'description': f'Africana AI order #{order.id}', 'callback_url': callback_url, 'notification_id': notification_id, 'billing_address': {'email_address': request.user.email or f'{request.user.username}@example.com', 'phone_number': order.delivery_phone, 'country_code': 'UG', 'first_name': request.user.first_name or request.user.username, 'last_name': request.user.last_name or 'User'}}, access_token=token)
    except Exception as exc:
        payment.status = 'failed'
        payment.save(update_fields=['status', 'updated_at'])
        logger.exception('Commerce Pesapal checkout failed: %s', exc)
        return JsonResponse({'error': 'Unable to start payment.'}, status=502)
    redirect_url = response.get('redirect_url') or response.get('RedirectUrl')
    payment.tracking_id = response.get('order_tracking_id') or response.get('OrderTrackingId')
    if not payment.tracking_id or not redirect_url:
        payment.status = 'failed'
        payment.raw_status = 'INVALID_PROVIDER_RESPONSE'
        payment.save(update_fields=['status', 'raw_status', 'updated_at'])
        logger.error('Pesapal returned an incomplete commerce checkout response: %s', response)
        return JsonResponse({'error': 'Payment provider did not return a valid checkout link.'}, status=502)
    payment.save(update_fields=['tracking_id', 'updated_at'])
    return JsonResponse({'order_id': order.id, 'tracking_id': payment.tracking_id, 'redirect_url': redirect_url, 'delivery_pin': delivery_pin, 'delivery_qr_token': str(order.delivery_qr_token)})


@login_required
def payment_callback(request):
    tracking_id = request.GET.get('OrderTrackingId') or request.GET.get('orderTrackingId')
    payment = CommercePayment.objects.select_related('order').filter(tracking_id=tracking_id, order__buyer=request.user).first()
    if not payment:
        return render(request, 'eshop/payment_result.html', {'payment': None, 'error': 'Payment reference was not found.'})

    ipn_response = commerce_payment_ipn(request)
    payment.refresh_from_db()
    payment.order.refresh_from_db()
    if ipn_response.status_code >= 400:
        return render(request, 'eshop/payment_result.html', {'payment': payment, 'error': 'We could not verify the payment yet. Please refresh shortly.'})
    return render(request, 'eshop/payment_result.html', {'payment': payment, 'error': None})


@csrf_exempt
def commerce_payment_ipn(request):
    if request.method not in {'GET', 'POST'}:
        return JsonResponse({'error': 'GET or POST required.'}, status=405)
    payload = request.POST if request.method == 'POST' else request.GET
    tracking_id = payload.get('OrderTrackingId') or payload.get('orderTrackingId')
    if not tracking_id:
        return JsonResponse({'error': 'OrderTrackingId is required.'}, status=400)
    payment = get_object_or_404(CommercePayment.objects.select_related('order'), tracking_id=tracking_id)
    try:
        from users.views import _pesapal_request
        token = _pesapal_request('post', 'Auth/RequestToken').get('token')
        payload = _pesapal_request('post', 'Transactions/GetTransactionStatus', json_data={'orderTrackingId': tracking_id}, access_token=token)
        status = str(payload.get('status') or payload.get('Status') or '').upper()
        with transaction.atomic():
            payment = CommercePayment.objects.select_for_update().select_related('order').get(pk=payment.pk)
            if status in {'COMPLETED', 'PAID', 'SUCCESS', 'SUCCESSFUL'}:
                payment.status = 'paid'
                payment.raw_status = status
                payment.provider_reference = str(payload.get('confirmation_code') or payload.get('payment_method') or '')
                payment.order.status = 'escrowed'
                payment.order.escrow_status = 'funded'
                payment.order.save(update_fields=['status', 'escrow_status'])
            elif status in {'FAILED', 'CANCELLED', 'CANCELED'}:
                payment.status = 'cancelled' if status != 'FAILED' else 'failed'
                payment.raw_status = status
                payment.order.status = 'cancelled'
                payment.order.save(update_fields=['status'])
            payment.save(update_fields=['status', 'raw_status', 'provider_reference', 'updated_at'])
    except Exception:
        logger.exception('Commerce Pesapal IPN verification failed.')
        return JsonResponse({'error': 'Unable to verify payment.'}, status=502)
    return JsonResponse({'status': 'accepted'})


@login_required
def merchant_dashboard(request):
    products = Product.objects.filter(vendor_user=request.user).select_related('inventory')
    all_orders = Order.objects.filter(order_items__product__vendor_user=request.user).distinct()
    orders = all_orders.order_by('-created_at')[:25]
    from social.models import MerchantAnalyticsEvent, SocialProfile
    analytics = MerchantAnalyticsEvent.objects.filter(merchant=request.user)
    profile = SocialProfile.objects.filter(user=request.user).first()
    completed_orders = all_orders.filter(status__in={'released', 'Completed'})
    monthly_counts = {
        row['month'].date().replace(day=1): row['sales']
        for row in completed_orders.annotate(month=TruncMonth('created_at')).values('month').annotate(sales=Count('id'))
    }
    current_month = timezone.localdate().replace(day=1)
    monthly_sales = []
    for offset in range(11, -1, -1):
        month_index = current_month.year * 12 + current_month.month - 1 - offset
        month_start = date(month_index // 12, month_index % 12 + 1, 1)
        monthly_sales.append({'label': month_start.strftime('%b %Y'), 'sales': monthly_counts.get(month_start, 0)})
    max_sales = max((month['sales'] for month in monthly_sales), default=0)
    for index, month in enumerate(monthly_sales):
        month['x'] = 10 + (index * 180 / max(len(monthly_sales) - 1, 1))
        month['y'] = 88 - ((month['sales'] / max(max_sales, 1)) * 68)
    sales_graph_points = ' '.join(f"{month['x']:.1f},{month['y']:.1f}" for month in monthly_sales)
    metrics = {
        'product_views': analytics.filter(event_type='product_view').count(),
        'reel_views': analytics.filter(event_type='reel_view').count(),
        'cart_adds': analytics.filter(event_type='cart_add').count(),
        'sales': completed_orders.count(),
        'revenue': completed_orders.aggregate(total=Sum('total_amount'))['total'] or 0,
    }
    return render(request, 'eshop/merchant_dashboard.html', {'products': products, 'orders': orders, 'metrics': metrics, 'social_profile': profile, 'monthly_sales': monthly_sales, 'sales_graph_points': sales_graph_points})


@login_required
def submit_verification(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    from social.models import SocialProfile
    profile, _ = SocialProfile.objects.get_or_create(user=request.user)
    profile.national_id_last4 = str(request.POST.get('national_id_last4', '')).strip()[-4:]
    profile.business_registration_ref = str(request.POST.get('business_registration_ref', '')).strip()[:100]
    profile.verification_status = 'pending'
    profile.save(update_fields=['national_id_last4', 'business_registration_ref', 'verification_status'])
    return JsonResponse({'status': profile.verification_status})


@login_required
def create_promotion(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    product = get_object_or_404(Product, id=request.POST.get('product_id'), vendor_user=request.user)
    try:
        daily_budget = Decimal(request.POST.get('daily_budget', '0'))
        bid_amount = Decimal(request.POST.get('bid_amount', '0'))
    except (InvalidOperation, TypeError):
        return JsonResponse({'error': 'Budget and bid must be valid amounts.'}, status=400)
    if daily_budget <= 0 or bid_amount <= 0:
        return JsonResponse({'error': 'Budget and bid must be positive.'}, status=400)
    campaign = PromotionCampaign.objects.create(merchant=request.user, product=product, daily_budget=daily_budget, bid_amount=bid_amount, status='active')
    return JsonResponse({'campaign_id': campaign.id, 'status': campaign.status})


@login_required
def affiliate_click(request):
    product = get_object_or_404(Product, id=request.GET.get('product_id'))
    creator_id = request.GET.get('creator_id')
    creator = User.objects.filter(id=creator_id).first() if creator_id else request.user
    AffiliateEvent.objects.create(creator=creator, product=product, event_type='click')
    return JsonResponse({'status': 'tracked', 'affiliate_url': product.affiliate_url or ''})


@login_required
def live_sessions(request):
    if request.method == 'GET':
        sessions = LiveShoppingSession.objects.filter(status__in={'scheduled', 'live'}).prefetch_related('pinned_products__product')[:50]
        return JsonResponse({'sessions': [{'id': session.id, 'title': session.title, 'host': session.host.username, 'status': session.status, 'language': session.language, 'stream_url': session.stream_url, 'products': [{'id': pin.product_id, 'name': pin.product.name} for pin in session.pinned_products.all()]} for session in sessions]})
    if request.method != 'POST':
        return JsonResponse({'error': 'GET or POST required.'}, status=405)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    title = str(payload.get('title', '')).strip()
    if not title:
        return JsonResponse({'error': 'title is required.'}, status=400)
    session = LiveShoppingSession.objects.create(host=request.user, title=title, language=payload.get('language', getattr(request.user, 'language', 'en')), stream_url=payload.get('stream_url', ''))
    for position, product_id in enumerate(payload.get('product_ids', [])):
        product = Product.objects.filter(id=product_id, vendor_user=request.user).first()
        if product:
            LivePinnedProduct.objects.create(session=session, product=product, position=position)
    return JsonResponse({'id': session.id, 'status': session.status}, status=201)


@login_required
def confirm_delivery(request, order_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    with transaction.atomic():
        order = get_object_or_404(Order.objects.select_for_update(), id=order_id)
        is_buyer = order.buyer_id == request.user.id
        is_vendor = order.order_items.filter(product__vendor_user=request.user).exists()
        if not (is_buyer or is_vendor):
            return JsonResponse({'error': 'You are not authorized to confirm this order.'}, status=403)
        if order.status not in {'delivered', 'escrowed'}:
            return JsonResponse({'error': 'Order is not ready for delivery confirmation.'}, status=409)
        supplied_pin = str(request.POST.get('pin') or request.headers.get('X-Delivery-PIN') or '').strip()
        supplied_qr = str(request.POST.get('qr_token') or request.headers.get('X-Delivery-QR') or '').strip()
        has_valid_credential = (
            bool(supplied_pin and order.delivery_pin_hash and check_password(supplied_pin, order.delivery_pin_hash))
            or supplied_qr == str(order.delivery_qr_token)
        )
        if is_vendor and not has_valid_credential:
            return JsonResponse({'error': 'A valid delivery PIN or QR token is required.'}, status=400)
        if is_vendor and not is_buyer:
            order.status = 'delivered'
            order.save(update_fields=['status'])
            return JsonResponse({'order_id': order.id, 'status': order.status, 'escrow_status': order.escrow_status})

        order.status = 'released'
        order.escrow_status = 'released'
        order.buyer_confirmed_at = timezone.now()
        order.funds_released_at = order.buyer_confirmed_at
        order.save(update_fields=['status', 'escrow_status', 'buyer_confirmed_at', 'funds_released_at'])
        for event in order.affiliate_events.filter(event_type='conversion'):
            AffiliatePayout.objects.filter(order=order, creator=event.creator).update(status='payable')
    return JsonResponse({'order_id': order.id, 'status': order.status, 'funds_released_at': order.funds_released_at.isoformat()})


@login_required
def delivery_qr(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    if order.buyer_id != request.user.id and not order.order_items.filter(product__vendor_user=request.user).exists():
        return HttpResponse('Not found.', status=404)
    if not order.delivery_qr_token:
        return HttpResponse('QR unavailable.', status=404)
    qr = qrcode.QRCode(box_size=8, border=2)
    qr.add_data(str(order.delivery_qr_token))
    qr.make(fit=True)
    image = qr.make_image(fill_color='#172b3a', back_color='white')
    output = BytesIO()
    image.save(output, format='PNG')
    return HttpResponse(output.getvalue(), content_type='image/png')


@login_required
def disburse_affiliate_payout(request, payout_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    payout = get_object_or_404(AffiliatePayout.objects.select_related('creator'), id=payout_id, creator=request.user)
    if payout.status != 'payable':
        return JsonResponse({'error': 'Payout is not payable.'}, status=409)
    social_profile = getattr(request.user, 'social_profile', None)
    payout_phone = str(request.POST.get('phone') or getattr(social_profile, 'whatsapp_number', '')).strip()
    payout_path = os.getenv('PESAPAL_PAYOUT_PATH', '').strip()
    if not payout_phone or not payout_path:
        return JsonResponse({'error': 'Configure a payout phone and PESAPAL_PAYOUT_PATH before disbursement.'}, status=503)
    try:
        from users.views import _pesapal_request
        result = _pesapal_request('post', payout_path, json_data={
            'amount': f'{payout.amount:.2f}',
            'currency': payout.order.currency,
            'recipient_phone': payout_phone,
            'reference': f'africana-affiliate-{payout.id}',
            'description': f'Affiliate commission for order #{payout.order_id}',
        })
    except Exception:
        logger.exception('Affiliate payout failed for payout %s', payout.id)
        return JsonResponse({'error': 'Payout provider request failed.'}, status=502)
    payout.status = 'paid' if str(result.get('status', '')).upper() in {'SUCCESS', 'COMPLETED', 'PAID'} else 'pending'
    payout.payout_phone = payout_phone
    payout.provider_reference = str(result.get('reference') or result.get('transaction_id') or result.get('id') or '')
    payout.provider_status = str(result.get('status') or result.get('message') or '')
    if payout.status == 'paid':
        payout.paid_at = timezone.now()
    payout.save(update_fields=['status', 'payout_phone', 'provider_reference', 'provider_status', 'paid_at'])
    return JsonResponse({'payout_id': payout.id, 'status': payout.status, 'provider_reference': payout.provider_reference})


@login_required
def voice_product_search(request):
    if request.method not in {'GET', 'POST'}:
        return JsonResponse({'error': 'GET or POST required.'}, status=405)
    payload = request.POST if request.method == 'POST' else request.GET
    query = str(payload.get('q') or payload.get('transcript') or '').strip()
    if not query:
        return JsonResponse({'error': 'transcript is required.'}, status=400)
    amount_match = re.search(r'(?:under|below|less than|nga|wansi wa)\s*([\d,]+)', query, re.IGNORECASE)
    max_price = Decimal(amount_match.group(1).replace(',', '')) if amount_match else None
    currency = next((code for code in Product.CURRENCY_CHOICES if code[0].lower() in query.lower()), ('UGX', ''))[0]
    search_text = re.split(r'\b(?:under|below|less than|nga|wansi wa)\b', query, maxsplit=1, flags=re.IGNORECASE)[0]
    search_text = re.sub(r'\b(?:find|search|show|me|please|high-waist|in|for)\b', ' ', search_text, flags=re.IGNORECASE)
    search_text = ' '.join(search_text.split()).strip()
    products = Product.objects.all()
    for term in search_text.split():
        products = products.filter(name__icontains=term)
    if max_price is not None:
        products = products.filter(price__lte=max_price, currency=currency)
    products = products.order_by('-impressions')[:20]
    return JsonResponse({'query': query, 'currency': currency, 'max_price': str(max_price) if max_price is not None else None, 'products': [{'id': product.id, 'name': product.name, 'price': str(product.price), 'currency': product.get_currency_code(), 'url': reverse('eshop:product_detail', args=[product.slug])} for product in products]})


@login_required
def whatsapp_catalog_sync(request):
    if request.method == 'POST' and request.POST.get('action') == 'connect':
        from .models import WhatsAppCatalogConnection
        connection, _ = WhatsAppCatalogConnection.objects.update_or_create(
            merchant=request.user,
            defaults={
                'phone_number_id': request.POST.get('phone_number_id', '').strip(),
                'catalog_id': request.POST.get('catalog_id', '').strip(),
                'access_token': request.POST.get('access_token', '').strip(),
                'is_active': True,
            },
        )
        return JsonResponse({'status': 'connected', 'connection_id': connection.id})
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    from .models import WhatsAppCatalogConnection
    connection = get_object_or_404(WhatsAppCatalogConnection, merchant=request.user, is_active=True)
    products = Product.objects.filter(vendor_user=request.user)
    synced = 0
    try:
        for product in products:
            response = requests.post(
                f'https://graph.facebook.com/v20.0/{connection.catalog_id}/products',
                params={'access_token': connection.access_token},
                json={'retailer_id': str(product.id), 'name': product.name, 'description': product.description[:500], 'price': int(product.price or 0) * 100, 'currency': product.currency, 'availability': 'in stock', 'url': request.build_absolute_uri(reverse('eshop:product_detail', args=[product.slug]))},
                timeout=20,
            )
            response.raise_for_status()
            synced += 1
        connection.last_synced_at = timezone.now()
        connection.last_sync_error = ''
        connection.save(update_fields=['last_synced_at', 'last_sync_error', 'updated_at'])
    except requests.RequestException as exc:
        connection.last_sync_error = str(exc)
        connection.save(update_fields=['last_sync_error', 'updated_at'])
        return JsonResponse({'error': 'WhatsApp catalog sync failed.', 'synced': synced}, status=502)
    return JsonResponse({'status': 'synced', 'synced': synced})
# ------------------------------------
# Helper Functions
# ------------------------------------

# Setup logging to track sync issues without crashing the site
logger = logging.getLogger(__name__)

@login_required
def sync_aliexpress_products(request):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect('eshop:product_list')

    try:
        api = AliexpressApi(
            settings.ALI_APP_KEY, 
            settings.ALI_APP_SECRET, 
            models.Language.EN, 
            models.Currency.USD, 
            settings.ALI_TRACKING_ID
        )

        # Hot-Selling Categories for Africa & Global Markets
       # AI, Smart Wearables, Robotics & Next-Gen Smart Home
       # Comprehensive Tech, AI, Smart Home, Smart Beauty & Personal Care Sync
       # Comprehensive Product Sync: AI, Smart Tech, Advanced Beauty, & Fast-Moving Everyday Innovations
        # Comprehensive Product Sync: AI, Smart Tech, Advanced Beauty, & Fast-Moving Everyday Innovations
       # Fully Expanded Product Sync: AI Gear, Wearables, Robotics, Smart Home, Dental/Cosmetic Tech & Daily Innovations
        search_groups = [
            # TOP PRIORITY: AI Smart Glasses
            {'query': 'fusion ai smart glasses mixed reality smart glasses fusion ai', 'count': 14},
            {'query': 'AI smart glasses video recording live stream audio', 'count': 12},
            {'query': 'smart glasses bluetooth audio wireless polarized sunglasses', 'count': 10},
            {'query': 'bone conduction smart glasses open ear audio headphones', 'count': 10},

            # NEXT: Mini Cameras, Necklaces with Cameras & Budget Action Cams
            {'query': 'mini spy camera cheap wireless security pocket cam', 'count': 14},
            {'query': 'sq11 mini camera full hd 1080p sports dv recorder spy clip', 'count': 12},
            {'query': 'action camera sports video recorder mini dvr small', 'count': 12},
            {'query': 'webcam micro camera usb plug play clear audio', 'count': 12},
            {'query': 'pendant necklace hidden mini spy camera audio video recorder', 'count': 12},

            # NEXT: Cheap, Top-selling Women-Focused Accessories & Beauty (Dropshipping-friendly)
            {'query': 'women earrings shell pearl fashion cheap top selling', 'count': 16},
            {'query': 'minimalist gold plated necklace women popular affordable', 'count': 14},
            {'query': 'korean skincare face roller jade gua sha affordable', 'count': 12},
            {'query': 'makeup brush set professional soft synthetic cheap', 'count': 14},
            {'query': 'false eyelashes volume mink look cheap top selling', 'count': 14},
            {'query': 'hair claw clip large acrylic trendy women cheap', 'count': 16},
            {'query': 'scrunchies set velvet hair elastic pretty cheap', 'count': 16},
            {'query': 'women crossbody purse small vintage cute cheap', 'count': 12},
            {'query': 'fashion sunglasses women polarized stylish cheap', 'count': 12},
            {'query': 'anklet bracelet women boho gold cheap top selling', 'count': 12},
            {'query': 'layered necklace set women bohemian cute affordable', 'count': 12},

            # NEXT: Beauty & Personal Care small appliances
            {'query': 'portable facial steamer nano face steamer home use cheap', 'count': 12},
            {'query': 'led face mask skincare phototherapy anti aging affordable', 'count': 10},
            {'query': 'nail art kit gel polish set cheap popular', 'count': 12},
            {'query': 'compact makeup mirror led light portable cheap', 'count': 12},

            # NEXT: Fashion & Activewear (Women)
            {'query': 'women leggings high waist seamless gym cheap popular', 'count': 12},
            {'query': 'seamless sports bra crop top women affordable', 'count': 12},
            {'query': 'boho summer dress women casual cute affordable', 'count': 14},

            # NEXT: Home & Lifestyle Accessories popular with women
            {'query': 'cute phone holder ring stand bling cheap top selling', 'count': 12},
            {'query': 'reusable makeup remover pads washable eco friendly cheap', 'count': 12},
            {'query': 'travel jewelry organizer pouch small cheap', 'count': 12},

            # NEXT: Fusion Products for Men & Women (kept some existing queries)
            {'query': 'women fusion boho modern ethnic fusion dress affordable', 'count': 14},
            {'query': 'women fusion street traditional hybrid dress cheap high quality', 'count': 14},
            {'query': 'fusion bags cheap travel tote crossbody fusion style', 'count': 12},

            # FALLBACK: Other tech & home categories
            {'query': 'smart home automation hub gateway zigbee wifi alexa assistant', 'count': 10},
            {'query': 'edge ai npu accelerator usb ai inference device', 'count': 10},
            {'query': 'ai voice assistant smart speaker compact bluetooth alexa assistant', 'count': 10},
            {'query': 'digital kitchen scale electronic food weight measuring tool precision lcd', 'count': 10},
            {'query': 'rechargeable mini neck fan portable bladeless mute wearable outdoor fans usb', 'count': 10},

             # TOP PRIORITY: AI Smart Glasses
            {'query': 'fusion ai smart glasses mixed reality smart glasses fusion ai', 'count': 14},
            {'query': 'AI smart glasses video recording live stream audio', 'count': 12},
            {'query': 'smart glasses bluetooth audio wireless polarized sunglasses', 'count': 10},
            {'query': 'bone conduction smart glasses open ear audio headphones', 'count': 10},

            # NEXT: Mini Cameras, Necklaces with Cameras & Budget Action Cams
            {'query': 'mini spy camera cheap wireless security pocket cam 5 dollars', 'count': 14},
            {'query': 'sq11 mini camera full hd 1080p sports dv recorder spy clip', 'count': 12},
            {'query': 'action camera sports video recorder mini dvr small under 10', 'count': 12},
            {'query': 'webcam micro camera usb plug play cheap clear audio 5', 'count': 12},
            {'query': 'pendant necklace hidden mini spy camera audio video recorder', 'count': 12},

            # NEXT: Fusion Products for Men & Women (fusion clothing + accessories)
            {'query': 'women fusion boho modern ethnic fusion dress affordable', 'count': 14},
            {'query': 'women fusion street traditional hybrid dress cheap high quality', 'count': 14},
            {'query': 'women fusion casual dress budget everyday stylish', 'count': 14},
            {'query': 'women fusion cheap quality dress affordable fusion wear', 'count': 14},
            {'query': 'mens fusion lightweight breathable fusion shirt cheap quality', 'count': 12},
            {'query': 'fusion bags cheap travel tote crossbody fusion style', 'count': 12},

            # NEXT: Smart Wearables & Accessories (rings, bangles, padlocks)
            {'query': 'smart ring nfc payment sleep tracker fitness tracker', 'count': 12},
            {'query': 'smart bangle fitness tracker waterproof health monitor', 'count': 12},
            {'query': 'smart padlock bluetooth fingerprint wifi outdoor security lock', 'count': 12},
            {'query': 'fingerprint thumb padlock bluetooth compact security lock', 'count': 12},
            {'query': 'biometric fingerprint padlock bluetooth rechargeable', 'count': 12},
            {'query': 'fingerprint padlock keyless smart portable outdoor security', 'count': 12},
            {'query': 'smart padlock keyless digital lock weatherproof outdoor security', 'count': 10},
            {'query': 'smart padlock bluetooth fingerprint lock security for bike gate', 'count': 10},
            {'query': 'usb rechargeable fingerprint padlock bluetooth anti-theft', 'count': 10},
            {'query': 'portable biometric padlock fingerprint keyless locker lock', 'count': 10},
            {'query': 'smart necklace pendant wearable nfc gps sos personal tracker', 'count': 10},
            {'query': 'smart necklace bluetooth fashion wearable pendant smart jewelry', 'count': 12},
            {'query': 'mini smart camera 1080p wireless ai tracking night vision', 'count': 14},
            {'query': '4k smart security camera ai detection wired wireless', 'count': 12},
            {'query': 'emo robot plush emotional robot companion toy smart robot', 'count': 10},
            {'query': 'programmable robot kit wifi bluetooth coding obstacle avoidance', 'count': 14},

            # NEXT: Programmable Robots & STEAM (education, hobby, AI companions)
            {'query': 'programmable robot kit wifi bluetooth coding obstacle avoidance', 'count': 14},
            {'query': 'programmable robotic car kit obstacle avoidance arduino rpi', 'count': 12},
            {'query': 'educational STEAM robot kit arduino coding STEM robotic arm kit', 'count': 12},
            {'query': 'DIY robot kit for kids programmable educational STEAM electronics', 'count': 12},

            # NEXT: Clothes (general high-demand categories)
            {'query': 'women evening party dress sexy slim-fit suspender solid color dress', 'count': 12},
            {'query': 'vintage summer dress women v-neck flowers printed casual beach dress', 'count': 12},
            {'query': "mens oversized t shirt summer breathable round neck short sleeve", 'count': 12},
            {'query': "mens shorts set casual stripe printed elastic waist two piece", 'count': 12},

            # NEXT: Luggage & Bags (cheap travel options)
            {'query': 'luggage travel backpack carry-on handbag womens tote', 'count': 12},
            {'query': 'cheap travel backpacks lightweight foldable tote bag', 'count': 12},

            # FALLBACK: Other categories (left intact)
            {'query': 'smart home automation hub gateway zigbee wifi alexa assistant', 'count': 10},
            {'query': 'edge ai npu accelerator usb ai inference device', 'count': 10},
            {'query': 'ai voice assistant smart speaker compact bluetooth alexa assistant', 'count': 10},
            {'query': 'digital kitchen scale electronic food weight measuring tool precision lcd', 'count': 10},
            {'query': 'rechargeable mini neck fan portable bladeless mute wearable outdoor fans usb', 'count': 10},
        ]
        created_count = 0
        updated_count = 0

        adult_blacklist = [
            # 'vibrator', 'sex toy', 'clitoris', 'clit', 'dildo', 'anal', 'nipple', 'masturbator',
            # 'porn', 'adult', 'erotic', 'sucking', 'thrusting', 'dirty', 'bondage',
            # 'orgasm', 'sexy toy', 'sex supplies', 'sensual', 'g spot', 'g-spot'
        ]

        for group in search_groups:
            try:
                # Avoid passing a risky sort parameter that may trigger API gateway 405
                items = api.get_products(
                    keywords=group['query'], 
                    page_size=group['count']
                )

                if not items or not hasattr(items, 'products') or not items.products:
                    logger.warning(f"AliExpress returned no products for query: {group['query']}")
                    continue

            except Exception as api_err:
                logger.error(f"AliExpress API error for query '{group['query']}': {api_err}")
                continue

            for item in items.products:
                try:
                    title_lower = str(getattr(item, 'product_title', '')).lower()
                    if any(term in title_lower for term in adult_blacklist):
                        continue

                    img_url = item.product_main_image_url
                    if img_url and img_url.startswith('//'):
                        img_url = f"https:{img_url}"
                    
                    price = Decimal(str(getattr(item, 'target_sale_price', '0.00')))
                    unique_slug = slugify(f"{item.product_title[:40]}-{item.product_id}")

                    obj, created = Product.objects.update_or_create(
                        external_id=str(item.product_id),
                        defaults={
                            'source': 'aliexpress',
                            'name': item.product_title[:200],
                            'slug': unique_slug,
                            'description': f"Global Hot-Seller. Top Rated. ID: {item.product_id}",
                            'price': price,
                            'currency': 'USD',
                            'affiliate_url': item.promotion_link, # Your Commission Link
                            'image_url': img_url,
                            'vendor_name': 'Global Hot-Sellers',
                            'is_negotiable': False,
                            'country': 'Global',
                            'whatsapp_number': 'EXTERNAL',
                        }
                    )
                    if created: created_count += 1
                    else: updated_count += 1
                except Exception:
                    continue

        # Remove any previously imported adult products that may have been added before filtering was enabled
        Product.objects.filter(
            name__iregex=r"(vibrator|sex toy|clitoris|clit|dildo|anal|nipple|masturbator|porn|adult|erotic|sucking|thrusting|g[ -]?spot)"
        ).delete()

        messages.success(request, f"Global Sync Complete! {created_count} hot-selling products added to your catalog.")
    except Exception as e:
        logger.exception("AliExpress sync failed")
        messages.error(request, f"Sync error: {str(e)}")

    return redirect('eshop:product_list')

def google_verification(request):
    """Verifies site ownership for Google Search Console."""
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    """Generates robots.txt for search engine crawlers."""
    lines = [
        "User-agent: *",
        "Allow: /",
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
@login_required
def get_user_cart(request):
    """Retrieves or creates the user's active cart based on the session key."""
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    
    # Prune old, inactive carts (older than 7 days)
    one_week_ago = timezone.now() - timedelta(days=7)
    Cart.objects.filter(updated_at__lt=one_week_ago, is_active=False).delete()

    cart, created = Cart.objects.get_or_create(
        session_key=session_key,
        defaults={'is_active': True}
    )
    return cart

# ------------------------------------
# E-Shop Core Views
# ------------------------------------
# assuming you already have this helper

@login_required
def product_list(request):
    """Lists all available products with search and referral tracking."""
    # Capture and validate referrer from URL (?ref=username)
    referrer = request.GET.get('ref')
    if referrer:
        try:
            ref_user = User.objects.get(username=referrer)
            if request.user != ref_user:
                request.session['active_referrer'] = ref_user.username
        except User.DoesNotExist:
            request.session.pop('active_referrer', None)

    products = Product.objects.annotate(
        promotion_bid=Max('promotion_campaigns__bid_amount', filter=Q(promotion_campaigns__status='active'))
    ).order_by('-promotion_bid', '-id')

    # Search and Filter Logic
    search_query = request.GET.get('search', '').strip()
    country_query = request.GET.get('country', '').strip()
    vendor_query = request.GET.get('vendor', '').strip()
    category_query = request.GET.get('category', '').strip()
    source_query = request.GET.get('source', '').strip()
    min_price_query = request.GET.get('min_price', '').strip()
    max_price_query = request.GET.get('max_price', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)
    if country_query:
        products = products.filter(country__icontains=country_query)
    if vendor_query:
        products = products.filter(vendor_name__icontains=vendor_query)
    if category_query:
        products = products.filter(category__iexact=category_query)
    if source_query:
        products = products.filter(source__iexact=source_query)
    if min_price_query:
        try:
            products = products.filter(price__gte=Decimal(min_price_query))
        except (InvalidOperation, ValueError):
            pass
    if max_price_query:
        try:
            products = products.filter(price__lte=Decimal(max_price_query))
        except (InvalidOperation, ValueError):
            pass

    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0

    return render(request, 'eshop/product_list.html', {
        'products': products,
        'category_choices': Product.CATEGORY_CHOICES,
        'cart': cart,
        'cart_total': cart_total,
        'search_query': search_query,
        'country_query': country_query,
        'vendor_query': vendor_query,
        'category_query': category_query,
        'source_query': source_query,
        'min_price_query': min_price_query,
        'max_price_query': max_price_query,
    })


@login_required
def save_language_preference(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    language = str(request.POST.get('language', '')).strip().lower()
    supported_languages = {'en', 'lg', 'sw', 'nyn', 'ach', 'xsm', 'teo', 'lue', 'alur', 'rw', 'rn', 'ln', 'yo', 'ha', 'ig', 'ak', 'zu', 'xh', 'sn', 'ny', 'am', 'om', 'fr', 'pt', 'ar'}
    if language not in supported_languages:
        return JsonResponse({'error': 'Unsupported language.'}, status=400)
    request.user.language = language
    request.user.save(update_fields=['language'])
    return JsonResponse({'status': 'saved', 'language': language})

@login_required
def add_product(request):
    """Handles the form for vendors to add a new product."""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(commit=False)
            product.vendor_user = request.user
            product.save()
            messages.success(request, f"🎉 Product '{product.name}' is now live!")
            return redirect('eshop:product_list')
    else:
        form = ProductForm()
    return render(request, 'eshop/add_product.html', {'form': form})


@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id, vendor_user=request.user)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Product '{product.name}' was updated.")
        return redirect('eshop:merchant_dashboard')
    return render(request, 'eshop/add_product.html', {'form': form, 'editing': True, 'product': product})


@login_required
def delete_product(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    product = get_object_or_404(Product, id=product_id, vendor_user=request.user)
    try:
        product.delete()
    except ProtectedError:
        messages.error(request, 'This product is linked to order history and cannot be deleted.')
    else:
        messages.success(request, 'Product deleted.')
    return redirect('eshop:merchant_dashboard')

@login_required
def product_detail(request, slug):
    """Displays detailed information for a specific product."""
    product = get_object_or_404(Product, slug=slug)
    try:
        from social.models import MerchantAnalyticsEvent
        if product.vendor_user_id:
            MerchantAnalyticsEvent.objects.create(merchant_id=product.vendor_user_id, product=product, event_type='product_view', visitor_key=request.session.session_key or '')
    except Exception:
        logger.exception('Product view analytics failed for product %s', product.id)
    
    # Check for referral link in URL
    referrer_username = request.GET.get('ref')
    
    if referrer_username:
        # Optimization: Only set the session if the referrer isn't the current user
        if referrer_username != request.user.username:
            request.session['active_referrer'] = referrer_username
            # Set the referral to last for 48 hours (in seconds)
            request.session.set_expiry(172800) 
        
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
    
    return render(request, 'eshop/product_detail.html', {
        'product': product,
        'cart': cart,
        'cart_total': cart_total,
    })
    
@login_required
def add_to_cart(request, product_id):
    """Adds a specific product to the user's active shopping cart."""
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)
    
    # Try to find existing item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, 
        product=product,
        defaults={'quantity': 1}
    )
    try:
        from social.models import MerchantAnalyticsEvent
        if product.vendor_user_id:
            MerchantAnalyticsEvent.objects.create(merchant_id=product.vendor_user_id, product=product, event_type='cart_add', visitor_key=request.session.session_key or '')
    except Exception:
        logger.exception('Cart analytics failed for product %s', product.id)
    
    if not created:
        # If item already exists, increase quantity
        cart_item.quantity = F('quantity') + 1
        cart_item.save()
        cart_item.refresh_from_db() 
        messages.success(request, f"📦 Added another '{product.name}' to your cart. Total: {cart_item.quantity}")
    else:
        messages.success(request, f"🛒 '{product.name}' has been added to your cart.")
        
    return redirect('eshop:view_cart')

@login_required
def view_cart(request):
    """Renders the shopping cart page."""
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0

    return render(request, 'eshop/cart.html', {
        'cart': cart,
        'cart_total': cart_total,
    })

@login_required
def remove_from_cart(request, item_id):
    """Removes an item entry from the user's cart."""
    cart = get_user_cart(request)
    try:
        item = CartItem.objects.get(id=item_id, cart=cart)
        product_name = item.product.name
        item.delete()
        messages.success(request, f"🗑️ '{product_name}' was removed from your cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "That item was not found in your cart.")
    
    return redirect('eshop:view_cart')



@login_required
def checkout_view(request):
    """Finalizes order record, attributes referral, and prepares vendor summary."""
    cart = get_user_cart(request)
    
    if not cart or not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('eshop:product_list')

    first_item = cart.items.first()
    currency_code = first_item.product.get_currency_code() if first_item else "KES"
    cart_total = cart.cart_total
    total_items_count = cart.items.aggregate(total=Sum('quantity'))['total'] or 0
   
    
    # 1. Retrieve Referrer from Session (captured in product_detail)
    referrer_username = request.session.get('active_referrer')
    referrer_user = None
    if referrer_username:
        referrer_user = User.objects.filter(username=referrer_username).first()

    # 2. Database Transaction: Create the Order record
    try:
        with transaction.atomic():
            # Create the main order
            order = Order.objects.create(
                buyer=request.user,
                referrer=referrer_user,
                total_amount=cart_total,
                status='Pending' # Wait for vendor confirmation to mark 'Completed'
            )

            running_commission = 0
            order_items_list = []

            for item in cart.items.all():
                # Snapshot the data in case product changes later
                price = item.product.negotiated_price or item.product.price
                commission = item.product.referral_commission * item.quantity
                
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_purchase=price,
                    commission_at_purchase=item.product.referral_commission
                )
                
                running_commission += commission
                order_items_list.append(f"- {item.quantity} x {item.product.name} @ {item.product.get_currency_code()} {price:,.0f}")

            # Update order with final calculated commission
            order.total_commission = running_commission
            order.save()

            # 3. Notification Logic (Initial "Pending" Alert)
            if referrer_user:
                Notification.objects.create(
                    user=referrer_user,
                    title="Referral tracked! 🎯",
                    message=f"Someone is checking out {first_item.product.name} using your link. You'll earn commission once the vendor completes the sale!"
                )

            # 4. Prepare the WhatsApp Message
            order_items_string = "\n".join(order_items_list)
            order_message = (
                f"Hello {item.product.vendor_name},\n\n"
                f"🎉 New order confirmed via Africana AI!\n\n"
                f"Order ID: #{order.id}\n"
                f"🛍️ Items:\n{order_items_string}\n\n"
                f"💰 Total: {first_item.product.get_currency_code()} {cart_total:,.0f}\n"
                f"👤 Buyer: {request.user.get_full_name() or request.user.username}\n"
                f"📞 Please contact me for delivery details."
            )

            # 5. Clear Cart & Referral Session
            # cart.items.all().delete()
            if 'active_referrer' in request.session:
                del request.session['active_referrer']

    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('eshop:cart_detail')

    context = {
        'order': order,
        'cart_total': cart_total,
        'total_items_count': total_items_count,
        'vendor': {'name': first_item.product.vendor_name, 'phone_number': first_item.product.whatsapp_number},
        'order_message': order_message,
    }

    return render(request, 'eshop/checkout.html', context)

# @login_required
# def delivery_location_view(request):
#     """Renders the map view for selecting a delivery location."""
#     return render(request, 'eshop/delivery_location.html')

@login_required
def delivery_location_view(request):
    """Renders the map view for selecting a delivery location with cart data."""
    cart = get_user_cart(request)
    
    # We pass the cart and the total so the JavaScript can 'see' them
    context = {
        'cart': cart,
        'cart_total': cart.cart_total,
    }
    return render(request, 'eshop/delivery_location.html', context)


@login_required
def payment_view(request):
    """Shows the in-app payment step after delivery details are saved."""
    cart = get_user_cart(request)
    delivery = request.session.get('delivery_details')
    if not cart.items.exists() or not delivery:
        messages.error(request, 'Please provide delivery details before payment.')
        return redirect('eshop:delivery_location')
    return render(request, 'eshop/payment.html', {
        'cart': cart,
        'cart_total': cart.cart_total,
        'currency': cart.items.first().product.get_currency_code(),
    })

@login_required
def process_delivery_location(request):
    """Processes and saves delivery details into the session."""
    if request.method == 'POST':
        address = (request.POST.get('address') or request.POST.get('address_line1') or '').strip()
        city = request.POST.get('city', '').strip()
        phone = request.POST.get('phone', '').strip()
        latitude = request.POST.get('latitude', 'N/A')
        longitude = request.POST.get('longitude', 'N/A')
        
        if not all([address, city, phone]):
             messages.error(request, "Please fill in all required delivery details (Address, City, Phone).")
             return redirect('eshop:delivery_location')

        request.session['delivery_details'] = {
            'address': address, 'city': city, 'phone': phone,
            'latitude': latitude, 'longitude': longitude,
        }
        
        messages.success(request, "Delivery location confirmed! Please proceed to order confirmation.")
        return redirect('eshop:payment')
        
    return redirect('eshop:delivery_location')
@login_required
def confirm_order_whatsapp(request):
    """Finalizes order in DB and redirects to WhatsApp."""
    cart = get_user_cart(request)
    delivery_details = request.session.pop('delivery_details', None)
    referrer_username = request.session.get('active_referrer')

    if not cart.items.exists() or not delivery_details:
        messages.error(request, "Session expired or cart empty.")
        return redirect('eshop:product_list')

    # 1. Determine Referrer
    referrer = None
    if referrer_username:
        referrer = User.objects.filter(username=referrer_username).first()

    # 2. Database Transaction for Order Consistency
    with transaction.atomic():
        order = Order.objects.create(
            buyer=request.user,
            referrer=referrer,
            total_amount=cart.cart_total,
            status='payment_pending'
        )

        total_comm = 0
        order_items_text = []
        first_item = cart.items.first()

        for item in cart.items.all():
            comm_per_unit = item.product.referral_commission or 0
            total_comm += (comm_per_unit * item.quantity)
            
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.negotiated_price or item.product.price,
                commission_at_purchase=comm_per_unit
            )
            order_items_text.append(f"- {item.quantity} x {item.product.name}")
        
        order.total_commission = total_comm
        order.save()

        # 3. Notification for the Referrer (if exists)
        if referrer:
            Notification.objects.create(
                user=referrer,
                title="Commission Earned! 💰",
                message=f"Success! Someone bought from your link. You earned {first_item.product.get_currency_code()} {total_comm:,.0f}."
            )

    # 4. FIX FOR SYNTAX ERROR: Prepare Message Body separately
    items_block = "\n".join(order_items_text)
    curr = first_item.product.get_currency_code()
    
    full_message = (
        f"Hello {first_item.product.vendor_name},\n"
        f"🎉 New order from Africana!\n\n"
        f"📍 Deliver to: {delivery_details['address']}, {delivery_details['city']}\n"
        f"📞 Contact: {delivery_details['phone']}\n\n"
        f"🛍️ Items:\n{items_block}\n\n"
        f"💰 Total: {curr} {order.total_amount:,.0f}"
    )

    whatsapp_url = f"https://wa.me/{first_item.product.whatsapp_number}?text={quote(full_message)}"

    # 5. Cleanup
    cart.items.all().delete()
    request.session.pop('active_referrer', None)

    return redirect(whatsapp_url)

def round_price(price, product_price_ref):
    """Rounds prices based on magnitude for localized currency standards (e.g., UGX)."""
    price = price.quantize(Decimal('0.00')) 
    if product_price_ref >= Decimal('100000'):
         return Decimal(round(price / Decimal('1000')) * Decimal('1000'))
    elif product_price_ref >= Decimal('1000'):
         return Decimal(round(price / Decimal('100')) * Decimal('100'))
    else:
         return price.quantize(Decimal('0.00')) 

def is_luganda(text):
    """Simple keyword-based detection for Luganda language."""
    text_lower = text.lower()
    luganda_keywords = [
        'nsaba', 'nzikiriza', 'ogulire', 'kikula', 'kitono', 'wansi',
        'ogatta', 'nsasule', 'mpola', 'sente', 'ogwa', 'tunda', 'muwendo',
        'kundagaano', 'kankendeze'
    ]
    if sum(1 for keyword in luganda_keywords if keyword in text_lower) >= 2:
        return True
    return False

def get_luganda_response(stage, price_str, curr, offer_text="omusaala gwo"):
    """Provides translated Luganda strings for the AI negotiator."""
    if stage == 'accept':
        return f"Wewawo! **{curr} {price_str}** tukoze endagaano. Twagasseeko ogubadde ogw'oluvannyuma. Kanda ku 'Lock In' wansi ofune eky'omuzingo kino. 🎉"
    elif stage == 'final_floor_rejection':
        return f"Mpulidde {offer_text}, naye nsonyiwa, **{curr} {price_str}** ogwo gwe musaala ogw'oluvannyuma nzekka gwe nsobola okuwa. Fuba okutuukirira. 🤝"
    elif stage == 'initial_ask_counter': 
        return f"Mpulidde ekirowoozo kyo. Okusooka, nina okuwa **{curr} {price_str}** (ekya 2% kiggyiddwako). Kiki eky'oluvannyuma ky’olina okuwa?"
    elif stage == 'mid_ask_counter':
        return f"Kuba nti obadde osaba, nkukendeezezzaako ku **{curr} {price_str}** (ekya 5% kiggyiddwako). Oli kumpi n'omusaala ogw'oluvannyuma. Wandiwadde omuwendo ogusinga guno?"
    elif stage == 'final_ask_counter':
        return f"Kino kye kiggya eky'oluvannyuma! Omuwendo ogusembayo gw'oyinza okufuna gwe **{curr} {price_str}** (ekya 10% kiggyiddwako). Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    elif stage == 'too_low_initial_counter':
        return f"Nsonyiwa, {offer_text} guli wansi nnyo. Kyokka, nina okutandikira ku **{curr} {price_str}** (2% off) okutandika endagaano. Fuba okukuwa omuwendo ogusinga."
    elif stage == 'default_query':
        return f"Nkyasobola okutegeera kye wategeeza. Fuba okuwa omusaala ogw'enkyukakyuka (nga '{curr} 80,000') oba nsaba nkukendeezeeko omuwendo. Genda mu maaso."
    elif stage == 'already_agreed':
        return f"Tugenze! Twakkiriziganyizza ku **{curr} {price_str}**. Kanda ku 'Lock In' wansi."
    elif stage == 'too_high_offer':
        return f"{offer_text} ogwo guli waggulu nnyo! Nnina okukuguliza ku **{curr} {price_str}** ogw'oluvannyuma. Kanda ku 'Lock In' ofune eky'omuzingo. 😊"
    elif stage == 'stage_one_offer': 
        return f"Mpulidde {offer_text}. Nga bwe tusalira, nina okuwa **{curr} {price_str}** (2% off). Omusango gw’olina okuddamu?"
    elif stage == 'stage_two_offer': 
        return f"Endagaano ennungi! Nkubuusa ku **{curr} {price_str}** (5% off). Oli kumpi n'omusaala ogw'oluvannyuma. Omuwendo gwo oguddako gwa ssente mmeka?"
    elif stage == 'final_offer': 
        return f"Nzigidde ebyo byonna byange! Omuwendo ogw'oluvannyuma gw'oyinza okufuna gwe **{curr} {price_str}**. Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    return "Error in translation simulation."

def get_gemini_negotiation_response(request, product, user_message, chat_history):
    """Main negotiation engine handling logic for price drops and deal closures."""
    product_price = product.price
    curr = product.get_currency_code()
    lang_key = f'negotiation_language_{product.slug}'
    session_language = request.session.get(lang_key)
    is_luganda_session = False
    
    if session_language == 'luganda':
        is_luganda_session = True
    elif session_language is None:
        if is_luganda(user_message):
            is_luganda_session = True
            request.session[lang_key] = 'luganda'
        else:
            request.session[lang_key] = 'english'

    def generate_response(stage_key, price=None, raw_offer_text=None):
        price_str = f"{price:,.0f}" if price is not None else "N/A"
        if is_luganda_session:
            return get_luganda_response(stage_key, price_str, curr, raw_offer_text)
        
        eng_responses = {
            'accept': f"Yes! {curr} {price_str} is an agreement. We have a deal! 🎉",
            'final_floor_rejection': f"I appreciate the offer of {raw_offer_text}, but it's too low. My price remains **{curr} {price_str}**.",
            'initial_ask_counter': f"I hear you! I can start at {curr} {price_str} (2% drop). What's your counter?",
            'mid_ask_counter': f"I will drop it again to {curr} {price_str} (5% drop). I have one final move left.",
            'final_ask_counter': f"Last chance! The lowest I can go is {curr} {price_str} (10% floor). What do you say?",
            'default_query': f"I'm not sure how to process that. Please make a clear offer (e.g., '{curr} 80,000').",
            'already_agreed': f"We've already agreed on {curr} {price_str}! Click 'Lock In' below. 🔒",
            'too_low_initial_counter': f"Offer of {raw_offer_text} is far too low. I'll drop to {curr} {price_str} to start.",
            'too_high_offer': f"That's higher than the original! We'll sell it for {curr} {price_str}. 😊",
            'stage_one_offer': f"I appreciate the offer of {raw_offer_text}. I can drop it to {curr} {price_str} (2% off).",
            'stage_two_offer': f"Good move! I will drop it to {curr} {price_str} (5% off). One final move left.",
            'final_offer': f"I'm going to my final floor! The lowest is {curr} {price_str}. Ready to lock it in? 🤝"
        }
        return eng_responses.get(stage_key, "An internal error occurred.")

    # Thresholds and Floors
    VENDOR_MIN_ENGAGEMENT = product_price * Decimal('0.70')
    FINAL_FLOOR = round_price(product_price * Decimal('0.90'), product_price)
    STAGE_TWO_PRICE = round_price(product_price * Decimal('0.95'), product_price)
    STAGE_ONE_PRICE = round_price(product_price * Decimal('0.98'), product_price)

    session_price = get_session_negotiated_price(request, product)
    last_ai_offer = session_price or product_price

    if session_price and session_price <= FINAL_FLOOR and session_price < product_price:
        return generate_response('already_agreed', round_price(session_price, product_price))

    offer = None
    # Use regex to find the first number in the message
    # It will extract "200" from "200ugsh" or "100,000" from "100,000"
    offer_match = re.search(r'(\d[\d,\.]*)', user_message)

    if offer_match:
        try:
            # Step 1: Remove commas and periods used for formatting
            val = offer_match.group(1).replace(',', '')
            # Step 2: Convert strictly to the number typed. 
            # If the user types 10, offer = 10. If they type 200, offer = 200.
            offer = Decimal(val).quantize(Decimal('0'))
            raw_offer_text = f"{curr} {offer:,.0f}"
        except (InvalidOperation, ValueError):
            offer = None

    if offer is None:
        user_msg_lower = user_message.lower()
        if any(phrase in user_msg_lower for phrase in ['reduce', 'lower', 'final price', 'best price', 'discount', 'kundagaano', 'kankendeze', 'mpola', 'wansi']):
            if last_ai_offer >= product_price * Decimal('0.99'):
                new_price = STAGE_ONE_PRICE
            elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'):
                new_price = STAGE_TWO_PRICE
            elif last_ai_offer > FINAL_FLOOR + Decimal('1'):
                new_price = FINAL_FLOOR
            else:
                return generate_response('final_floor_rejection', FINAL_FLOOR, raw_offer_text)

            set_session_negotiated_price(request, product, new_price)
            return generate_response('initial_ask_counter' if new_price == STAGE_ONE_PRICE else ('mid_ask_counter' if new_price == STAGE_TWO_PRICE else 'final_ask_counter'), new_price)
        return generate_response('default_query')

    if offer < VENDOR_MIN_ENGAGEMENT:
        if last_ai_offer >= product_price * Decimal('0.99'):
            set_session_negotiated_price(request, product, STAGE_ONE_PRICE)
            return generate_response('too_low_initial_counter', STAGE_ONE_PRICE, raw_offer_text)
        return generate_response('final_floor_rejection', last_ai_offer, raw_offer_text)

    if offer > product_price:
        set_session_negotiated_price(request, product, product_price)
        return generate_response('too_high_offer', product_price, raw_offer_text)

    if offer >= FINAL_FLOOR:
        final_p = round_price(offer if offer < product_price else product_price, product_price)
        set_session_negotiated_price(request, product, final_p)
        return generate_response('accept', final_p)

    if last_ai_offer >= product_price * Decimal('0.99'):
        new_price = STAGE_ONE_PRICE
        set_session_negotiated_price(request, product, new_price)
        return generate_response('stage_one_offer', new_price, raw_offer_text)
    elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'):
        new_price = STAGE_TWO_PRICE
        set_session_negotiated_price(request, product, new_price)
        return generate_response('stage_two_offer', new_price, raw_offer_text)
    elif last_ai_offer > FINAL_FLOOR + Decimal('1'):
        set_session_negotiated_price(request, product, FINAL_FLOOR)
        return generate_response('final_offer', FINAL_FLOOR)
    else:
        return generate_response('final_floor_rejection', FINAL_FLOOR, raw_offer_text)


def get_session_negotiated_price(request, product):
    value = request.session.get(f'negotiated_price_{product.slug}')
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return None

def set_session_negotiated_price(request, product, price):
    request.session[f'negotiated_price_{product.slug}'] = str(price)
    request.session.modified = True

def clear_session_negotiation(request, slug):
    for key in [
        f'chat_history_{slug}',
        f'negotiated_price_{slug}',
        f'accepted_price_{slug}',
        f'negotiation_language_{slug}',
    ]:
        request.session.pop(key, None)


def get_ai_response(request, product, user_message, chat_history):
    """Wrapper function to trigger the AI negotiation response."""
    return get_gemini_negotiation_response(request, product, user_message, chat_history)

@login_required
def ai_negotiation_view(request, slug):
    """View to handle the chat interface for AI price negotiation."""
    product = get_object_or_404(Product, slug=slug)
    curr = product.get_currency_code()
    if not product.is_negotiable:
        messages.error(request, f"Price negotiation is not available for {product.name}.")
        return redirect('eshop:product_detail', slug=slug)

    form = NegotiationForm(request.POST or None)
    chat_history = request.session.get(f'chat_history_{slug}', None)
    
    if chat_history is None:
        initial_greeting = f"Hello! I'm the AI Negotiator, and I'm ready to find you a great price. The original price for **{product.name}** is {curr} {product.price:,.0f}. What is your first offer?"
        chat_history = [{'role': 'ai', 'text': initial_greeting}]

    if request.method == 'POST' and form.is_valid():
        user_message = form.cleaned_data['user_message']
        chat_history.append({'role': 'user', 'text': user_message})
        ai_response_text = get_ai_response(request, product, user_message, chat_history)
        chat_history.append({'role': 'ai', 'text': ai_response_text})
        request.session[f'chat_history_{slug}'] = chat_history
        return redirect('eshop:ai_negotiation', slug=slug)

    negotiated_price = get_session_negotiated_price(request, product)
    is_negotiation_active = negotiated_price and negotiated_price <= product.price * Decimal('0.90')

    context = {
        'product': product,
        'form': form,
        'chat_history': chat_history,
        'is_negotiation_active': is_negotiation_active,
        'final_price': negotiated_price
    }
    return render(request, 'eshop/ai_negotiation.html', context)

@login_required
def accept_negotiated_price(request, slug):
    """Confirms the negotiated price and cleans up negotiation session state."""
    product = get_object_or_404(Product, slug=slug)
    curr = product.get_currency_code()
    negotiated_price = get_session_negotiated_price(request, product)

    if negotiated_price and negotiated_price <= product.price:
        request.session[f'accepted_price_{slug}'] = str(negotiated_price)
        request.session.pop(f'chat_history_{slug}', None)
        request.session.pop(f'negotiation_language_{slug}', None)
        request.session.pop(f'negotiated_price_{slug}', None)
        messages.success(request, f"🎉 Negotiated price of {curr} {negotiated_price:,.0f} accepted!")
        return redirect('eshop:product_detail', slug=slug)

    messages.error(request, "Oops! You must successfully negotiate first.")
    return redirect('eshop:ai_negotiation', slug=slug)

@login_required
def export_products_json(request):
    """Exports all products into a JSON file for backup or external use."""
    products = Product.objects.all()
    data = serialize('json', products, fields=('name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'language_tag'))
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="products.json"'
    return response

@login_required
def buy_now(request, product_id):
    """
    Decision logic: Redirect to WhatsApp for local items, 
    or to the Affiliate Link for AliExpress items.
    """
    product = get_object_or_404(Product, id=product_id)

    if product.source == 'aliexpress' and product.affiliate_url:
        # 1. Track the 'Order' in your DB so you know someone clicked your link
        Order.objects.create(
            buyer=request.user,
            total_amount=product.price,
            status='created',
            total_commission=product.referral_commission # If defined
        )
        
        # 2. Redirect the user to AliExpress to complete the purchase
        return redirect(product.affiliate_url)

    # 3. Otherwise, proceed to your local WhatsApp delivery flow
    return redirect('eshop:delivery_location')


def reset_negotiation(request, slug):
    """Clears the chat history and negotiated price for a specific product session."""
    clear_session_negotiation(request, slug)
    messages.info(request, "Negotiation history has been cleared.")
    return redirect('eshop:ai_negotiation', slug=slug)


# TEMPORARY: Delete this view after running the deletion command
# from django.contrib.auth.decorators import user_passes_test

# @user_passes_test(lambda u: u.is_superuser)  # Only superuser can trigger this
# def temporary_delete_ali_products(request):
#     """Temporary view to delete unused AliExpress products while preserving order history. Delete this view after running."""
#     # Find all AliExpress product IDs that are tied to existing orders
#     ordered_product_ids = OrderItem.objects.filter(
#         product__source='aliexpress'
#     ).values_list('product_id', flat=True).distinct()
    
#     # Delete only AliExpress products that have NEVER been ordered
#     unordered_products = Product.objects.filter(source='aliexpress').exclude(id__in=ordered_product_ids)
#     deleted_count, _ = unordered_products.delete()
    
#     skipped_count = ordered_product_ids.count() if ordered_product_ids else 0
    
#     return HttpResponse(
#         f"Cleanup complete! Deleted {deleted_count} unused AliExpress products. "
#         f"Preserved {skipped_count} products because they are linked to order history. "
#         f"Remember to delete this route and view from the code."
#     )
  
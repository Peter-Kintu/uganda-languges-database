import json
from datetime import timedelta
from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from eshop.models import Order
from .models import CourierProvider, DeliveryQuote, Shipment, TrackingEvent
from .services import CourierRegistry


@login_required
def create_quote(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    provider_code = request.GET.get('provider', 'mock')
    provider, _ = CourierProvider.objects.get_or_create(code=provider_code, defaults={'name': provider_code.title()})
    result = CourierRegistry.get(provider.code).quote(order=order)
    quote = DeliveryQuote.objects.create(
        order=order, provider=provider, amount=result.amount, currency=result.currency,
        eta_minutes=result.eta_minutes, expires_at=timezone.now() + timedelta(minutes=15),
    )
    return JsonResponse({'quote_id': str(quote.quote_id), 'amount': str(quote.amount), 'currency': quote.currency, 'eta_minutes': quote.eta_minutes, 'expires_at': quote.expires_at.isoformat()})


@login_required
def dispatch_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    quote = order.delivery_quotes.filter(status='quoted', expires_at__gt=timezone.now()).order_by('-created_at').first()
    if not quote:
        return JsonResponse({'error': 'A valid delivery quote is required.'}, status=400)
    if order.status not in {'escrowed', 'dispatching'}:
        return JsonResponse({'error': 'Only paid escrow orders can be dispatched.'}, status=409)
    result = CourierRegistry.get(quote.provider.code).dispatch(order=order, quote=quote)
    shipment = Shipment.objects.create(order=order, provider=quote.provider, external_id=result.external_id, tracking_url=result.tracking_url, dispatched_at=timezone.now(), status='assigned')
    order.status = 'dispatching'
    order.save(update_fields=['status'])
    TrackingEvent.objects.create(shipment=shipment, status='assigned', note='Courier dispatch created.', external_event_id=str(uuid4()))
    return JsonResponse({'shipment_id': shipment.external_id, 'status': shipment.status, 'tracking_url': shipment.tracking_url})


@login_required
def track_shipment(request, external_id):
    shipment = get_object_or_404(Shipment.objects.prefetch_related('tracking_events'), external_id=external_id, order__buyer=request.user)
    return JsonResponse({'shipment_id': shipment.external_id, 'status': shipment.status, 'tracking_url': shipment.tracking_url, 'events': [{'status': event.status, 'note': event.note, 'created_at': event.created_at.isoformat()} for event in shipment.tracking_events.all()]})


@csrf_exempt
def provider_webhook(request, provider_code):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required.'}, status=405)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    external_id = payload.get('external_id') or payload.get('tracking_id')
    status = payload.get('status')
    if not external_id or status not in dict(Shipment.STATUS_CHOICES):
        return JsonResponse({'error': 'external_id and a valid status are required.'}, status=400)
    shipment = get_object_or_404(Shipment, external_id=external_id, provider__code=provider_code)
    shipment.status = status
    if status == 'delivered':
        shipment.delivered_at = timezone.now()
        shipment.order.status = 'delivered'
        shipment.order.save(update_fields=['status'])
    shipment.save(update_fields=['status', 'delivered_at', 'updated_at'])
    TrackingEvent.objects.get_or_create(shipment=shipment, external_event_id=payload.get('event_id') or str(uuid4()), defaults={'status': status, 'note': payload.get('note', '')})
    return JsonResponse({'status': 'accepted'})

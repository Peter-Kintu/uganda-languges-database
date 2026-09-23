import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from eshop.models import Order
from .models import CourierProvider, DeliveryQuote, DriverProfile, RideLocation, RidePayment, RideRating, RideRequest, SafetyReport, Shipment, SupportTicket, TrackingEvent
from .services import CourierRegistry, calculate_ride_fare, match_nearest_driver, whatsapp_notification_link


def ride_home(request):
    return render(request, 'logistics/ride_home.html')


@login_required
def driver_home(request):
    driver = DriverProfile.objects.filter(user=request.user).first()
    rides = []
    if driver:
        rides = RideRequest.objects.filter(
            driver=driver,
            status__in=['assigned', 'arrived', 'in_progress'],
        ).select_related('rider')
    return render(request, 'logistics/driver_home.html', {'driver': driver, 'rides': rides})


@login_required
def driver_register(request):
    driver = DriverProfile.objects.filter(user=request.user).first()
    if request.method == 'POST':
        phone = str(request.POST.get('phone', '')).strip()
        vehicle_plate = str(request.POST.get('vehicle_plate', '')).strip()
        vehicle_type = request.POST.get('vehicle_type', 'standard')
        if not phone or not vehicle_plate or vehicle_type not in dict(DriverProfile.VEHICLE_CHOICES):
            return render(request, 'logistics/driver_register.html', {
                'driver': driver,
                'error': 'Phone, vehicle type, and plate number are required.',
            }, status=400)
        driver, _ = DriverProfile.objects.update_or_create(user=request.user, defaults={
            'phone': phone,
            'whatsapp_phone': str(request.POST.get('whatsapp_phone', '')).strip(),
            'vehicle_type': vehicle_type,
            'vehicle_make': str(request.POST.get('vehicle_make', '')).strip(),
            'vehicle_plate': vehicle_plate,
            'status': 'pending',
        })
        return render(request, 'logistics/driver_register.html', {'driver': driver, 'submitted': True})
    return render(request, 'logistics/driver_register.html', {'driver': driver})


def _json_body(request):
    if request.content_type == 'application/json':
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return None
    return request.POST


def _decimal(value):
    if value in (None, ''):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@login_required
@require_http_methods(['POST'])
def request_ride(request):
    throttle_key = f'ride-request:{request.user.pk}:{request.META.get("REMOTE_ADDR", "unknown")}'
    if cache.get(throttle_key):
        return JsonResponse({'error': 'Please wait before requesting another ride.'}, status=429)
    if RideRequest.objects.filter(rider=request.user, status__in=['requested', 'matching', 'assigned', 'arrived', 'in_progress']).exists():
        return JsonResponse({'error': 'You already have an active ride.'}, status=409)
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    required = ['pickup', 'dropoff']
    if any(not str(payload.get(field, '')).strip() for field in required):
        return JsonResponse({'error': 'Pickup and drop-off landmarks are required.'}, status=400)
    ride_type = payload.get('ride_type', 'standard')
    payment_method = payload.get('payment', 'Mobile Money').lower()
    payment_method = {'mobile money': 'momo', 'mtn momo': 'momo', 'airtel money': 'airtel'}.get(payment_method, payment_method)
    if ride_type not in dict(RideRequest.RIDE_TYPES) or payment_method not in dict(RideRequest.PAYMENT_METHODS):
        return JsonResponse({'error': 'Unsupported ride or payment type.'}, status=400)
    coordinates = [_decimal(payload.get(key)) for key in ('pickup_latitude', 'pickup_longitude', 'dropoff_latitude', 'dropoff_longitude')]
    fare = calculate_ride_fare(ride_type=ride_type, pickup_latitude=coordinates[0], pickup_longitude=coordinates[1], dropoff_latitude=coordinates[2], dropoff_longitude=coordinates[3])
    ride = RideRequest.objects.create(
        rider=request.user, pickup_landmark=str(payload['pickup']).strip(), dropoff_landmark=str(payload['dropoff']).strip(),
        pickup_latitude=coordinates[0], pickup_longitude=coordinates[1], dropoff_latitude=coordinates[2], dropoff_longitude=coordinates[3],
        ride_type=ride_type, payment_method=payment_method, status='matching', estimated_fare_min=fare.minimum,
        estimated_fare_max=fare.maximum, distance_km=fare.distance_km, eta_minutes=fare.eta_minutes,
    )
    cache.set(throttle_key, True, timeout=10)
    RidePayment.objects.create(ride=ride, provider=payment_method, amount=fare.maximum)
    driver = match_nearest_driver(ride)
    if driver:
        ride.driver = driver
        ride.status = 'assigned'
        ride.assigned_at = timezone.now()
        ride.save(update_fields=['driver', 'status', 'assigned_at', 'updated_at'])
    return JsonResponse({
        'ride_id': ride.pk, 'status': ride.status, 'fare_min': fare.minimum, 'fare_max': fare.maximum,
        'distance_km': str(fare.distance_km), 'eta_minutes': fare.eta_minutes, 'confidence': fare.confidence,
        'driver': {'name': driver.user.get_full_name() or driver.user.username, 'phone': driver.phone, 'vehicle_plate': driver.vehicle_plate} if driver else None,
        'whatsapp_link': whatsapp_notification_link(driver.whatsapp_phone or driver.phone, f'Ride {ride.pk} assigned') if driver else '',
    }, status=201)


@login_required
@require_http_methods(['GET'])
def ride_history(request):
    rides = RideRequest.objects.filter(rider=request.user).select_related('driver__user')[:50]
    return JsonResponse({'rides': [
        {'id': ride.pk, 'pickup': ride.pickup_landmark, 'dropoff': ride.dropoff_landmark, 'status': ride.status,
         'fare': f'UGX {ride.estimated_fare_min:,} - {ride.estimated_fare_max:,}', 'requested_at': ride.requested_at.isoformat(),
         'driver': ride.driver.user.get_full_name() if ride.driver else None}
        for ride in rides
    ]})


@login_required
@require_http_methods(['POST'])
def register_driver(request):
    payload = _json_body(request)
    if payload is None:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)
    required = ['phone', 'vehicle_plate', 'vehicle_type']
    if any(not str(payload.get(field, '')).strip() for field in required):
        return JsonResponse({'error': 'Phone, vehicle type, and plate are required.'}, status=400)
    driver, _ = DriverProfile.objects.update_or_create(user=request.user, defaults={
        'phone': payload['phone'], 'whatsapp_phone': payload.get('whatsapp_phone', ''),
        'vehicle_type': payload['vehicle_type'], 'vehicle_make': payload.get('vehicle_make', ''),
        'vehicle_plate': payload['vehicle_plate'], 'status': 'pending',
    })
    return JsonResponse({'driver_id': driver.pk, 'status': driver.status})


@login_required
@require_http_methods(['POST'])
def driver_location(request):
    driver = get_object_or_404(DriverProfile, user=request.user, status='verified')
    payload = _json_body(request) or {}
    latitude = _decimal(payload.get('latitude'))
    longitude = _decimal(payload.get('longitude'))
    if latitude is None or longitude is None:
        return JsonResponse({'error': 'Latitude and longitude are required.'}, status=400)
    driver.latitude, driver.longitude, driver.last_location_at = latitude, longitude, timezone.now()
    driver.is_available = bool(payload.get('available', driver.is_available))
    driver.save(update_fields=['latitude', 'longitude', 'last_location_at', 'is_available', 'updated_at'])
    ride = RideRequest.objects.filter(driver=driver, status__in=['assigned', 'arrived', 'in_progress']).first()
    if ride:
        RideLocation.objects.create(ride=ride, driver=driver, latitude=latitude, longitude=longitude, accuracy_meters=payload.get('accuracy_meters'))
    return JsonResponse({'status': 'updated', 'ride_id': ride.pk if ride else None})


@login_required
@require_http_methods(['GET', 'POST'])
def ride_status(request, ride_id):
    ride = get_object_or_404(RideRequest.objects.select_related('driver__user'), pk=ride_id)
    is_driver = ride.driver and ride.driver.user_id == request.user.id
    if ride.rider_id != request.user.id and not is_driver:
        return JsonResponse({'error': 'Ride access denied.'}, status=403)
    if request.method == 'POST':
        payload = _json_body(request) or {}
        next_status = payload.get('status')
        allowed = {'arrived', 'in_progress', 'completed'} if is_driver else {'cancelled'}
        if next_status not in allowed:
            return JsonResponse({'error': 'Invalid status transition.'}, status=400)
        ride.status = next_status
        if next_status == 'completed':
            ride.completed_at = timezone.now()
            ride.driver.completed_trips += 1
            ride.driver.is_available = True
            ride.driver.save(update_fields=['completed_trips', 'is_available', 'updated_at'])
            ride.save(update_fields=['status', 'completed_at', 'updated_at'])
        else:
            ride.save(update_fields=['status', 'updated_at'])
    return JsonResponse({'ride_id': ride.pk, 'status': ride.status, 'driver': {'name': ride.driver.user.get_full_name() or ride.driver.user.username, 'phone': ride.driver.phone} if ride.driver else None})


@login_required
@require_http_methods(['GET'])
def ride_tracking(request, ride_id):
    ride = get_object_or_404(RideRequest.objects.select_related('driver__user'), pk=ride_id)
    is_driver = ride.driver and ride.driver.user_id == request.user.id
    if ride.rider_id != request.user.id and not is_driver:
        return JsonResponse({'error': 'Ride access denied.'}, status=403)
    latest = ride.locations.first()
    driver_location = None
    if ride.driver and ride.driver.latitude is not None:
        driver_location = {'latitude': str(ride.driver.latitude), 'longitude': str(ride.driver.longitude), 'recorded_at': ride.driver.last_location_at.isoformat() if ride.driver.last_location_at else None}
    return JsonResponse({'ride_id': ride.pk, 'status': ride.status, 'driver_location': driver_location, 'path': [
        {'latitude': str(location.latitude), 'longitude': str(location.longitude), 'recorded_at': location.recorded_at.isoformat()}
        for location in ride.locations.all()[:50]
    ], 'last_ping': latest.recorded_at.isoformat() if latest else None})


@login_required
@require_http_methods(['POST'])
def rate_ride(request, ride_id):
    ride = get_object_or_404(RideRequest, pk=ride_id, rider=request.user, status='completed')
    payload = _json_body(request) or {}
    try:
        score = int(payload.get('score'))
    except (TypeError, ValueError):
        score = 0
    if not ride.driver or score not in range(1, 6):
        return JsonResponse({'error': 'A completed ride and score from 1 to 5 are required.'}, status=400)
    rating = RideRating.objects.create(ride=ride, rider=request.user, driver=ride.driver, score=score, comment=payload.get('comment', ''))
    return JsonResponse({'rating_id': rating.pk, 'status': 'saved'})


@login_required
@require_http_methods(['POST'])
def safety_report(request, ride_id):
    ride = get_object_or_404(RideRequest, pk=ride_id)
    if ride.rider_id != request.user.id and (not ride.driver or ride.driver.user_id != request.user.id):
        return JsonResponse({'error': 'Ride access denied.'}, status=403)
    payload = _json_body(request) or {}
    report = SafetyReport.objects.create(ride=ride, reporter=request.user, category=payload.get('category', 'other'), details=payload.get('details', ''))
    if report.category == 'emergency':
        SupportTicket.objects.create(requester=request.user, ride=ride, subject='Emergency ride alert', details=report.details, priority='urgent')
    return JsonResponse({'report_id': report.pk, 'status': report.status, 'emergency_contact': '+256000000000'})


@login_required
@require_http_methods(['POST'])
def create_support_ticket(request):
    payload = _json_body(request) or {}
    ride = None
    if payload.get('ride_id'):
        ride = get_object_or_404(RideRequest, pk=payload['ride_id'])
        if ride.rider_id != request.user.id and (not ride.driver or ride.driver.user_id != request.user.id):
            return JsonResponse({'error': 'Ride access denied.'}, status=403)
    subject = str(payload.get('subject', '')).strip()
    details = str(payload.get('details', '')).strip()
    if not subject or not details:
        return JsonResponse({'error': 'Subject and details are required.'}, status=400)
    ticket = SupportTicket.objects.create(requester=request.user, ride=ride, subject=subject, details=details, priority=payload.get('priority', 'normal'))
    return JsonResponse({'ticket_id': ticket.pk, 'status': ticket.status})


@csrf_exempt
@require_http_methods(['POST'])
def mobile_money_webhook(request, provider_code):
    payload = _json_body(request)
    if payload is None or provider_code not in {'momo', 'airtel'}:
        return JsonResponse({'error': 'Invalid provider or JSON.'}, status=400)
    payment = get_object_or_404(RidePayment, reference=payload.get('reference'), provider=provider_code)
    status = payload.get('status')
    if status not in {'paid', 'failed'}:
        return JsonResponse({'error': 'A paid or failed status is required.'}, status=400)
    payment.status = status
    payment.provider_transaction_id = payload.get('transaction_id', '')
    payment.save(update_fields=['status', 'provider_transaction_id', 'updated_at'])
    return JsonResponse({'status': 'accepted'})


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

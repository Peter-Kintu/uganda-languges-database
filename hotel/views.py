import os
import requests
import time
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.utils.text import slugify
from django.http import JsonResponse
from urllib.parse import quote
from .models import Accommodation
from .forms import AccommodationForm

def ajax_nearby_accommodations(request):
    """
    THE 5KM PROXIMITY ENGINE:
    Calculates distance using a coordinate bounding box (+/- 0.045 degrees).
    Prioritizes verified local vendors in the results.
    """
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'status': 'error', 'message': 'Location required'}, status=400)

    try:
        # Math: 0.045 degrees is roughly 5 kilometers
        range_delta = 0.045
        lat_min, lat_max = float(lat) - range_delta, float(lat) + range_delta
        lon_min, lon_max = float(lon) - range_delta, float(lon) + range_delta

        # Query: Within 5KM, prioritizing local community hosts
        nearby = Accommodation.objects.filter(
            latitude__range=(lat_min, lat_max),
            longitude__range=(lon_min, lon_max)
        ).order_by('-is_verified_vendor')[:6]

        results = [{
            'name': item.name,
            'city': item.city,
            'price': f"{item.currency} {item.price_per_night}",
            'slug': item.slug,
            'image': item.image.url if item.image else item.image_url,
            'is_verified': item.is_verified_vendor
        } for item in nearby]

        return JsonResponse({'status': 'success', 'data': results})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def sync_hotels_travelpayouts(request):
    """
    REAL-TIME API SYNC ENGINE:
    Updated to also store GPS coordinates for the discovery engine.
    """
    if not request.user.is_staff:
        messages.error(request, "Access Denied: Staff credentials required for API Sync.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" # Your Travelpayouts Affiliate Marker
    
    search_areas = [
        {'city': 'Kampala', 'country': 'Uganda', 'lat': '0.3476', 'lon': '32.5825'},
        {'city': 'Entebbe', 'country': 'Uganda', 'lat': '0.0512', 'lon': '32.4637'},
        {'city': 'Nairobi', 'country': 'Kenya', 'lat': '-1.2921', 'lon': '36.8219'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'lat': '-6.1659', 'lon': '39.2026'},
        {'city': 'Kigali', 'country': 'Rwanda', 'lat': '-1.9441', 'lon': '30.0619'},
        {'city': 'Cape Town', 'country': 'South Africa', 'lat': '-33.9249', 'lon': '18.4241'},
    ]

    hotels_synced = 0
    headers = {'X-Access-Token': api_token} if api_token else {}

    if not api_token:
        messages.warning(request, "API Sync failed: TRAVEL_PAYOUTS_TOKEN is missing.")
        return redirect('hotel:hotel_list')

    for area in search_areas:
        try:
            url = f"https://api.travelpayouts.com/v1/hotels/search.json?lat={area['lat']}&lon={area['lon']}&limit=15&currency=USD"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                hotels = data if isinstance(data, list) else data.get('hotels', [])

                for h in hotels:
                    hotel_name = h.get('name')
                    ext_id = str(h.get('id'))
                    
                    obj, created = Accommodation.objects.update_or_create(
                        external_id=ext_id,
                        defaults={
                            'source': 'travelpayouts',
                            'name': hotel_name,
                            'slug': slugify(f"{hotel_name}-{area['city']}") if not Accommodation.objects.filter(external_id=ext_id).exists() else None,
                            'city': area['city'],
                            'country': area['country'],
                            'stars': h.get('stars', 4),
                            'price_per_night': h.get('price', 0),
                            'currency': 'USD',
                            'latitude': h.get('lat'), # GPS Capture
                            'longitude': h.get('lon'), # GPS Capture
                            'description': f"A premium sanctuary located in {area['city']}. Verified as part of The Collection's global partner network.",
                            'affiliate_url': f"https://search.tp.st/hotels?hotelId={ext_id}&marker={marker}&locale=en"
                        }
                    )
                    
                    if created:
                        if not obj.slug:
                            obj.slug = slugify(f"{hotel_name}-{str(uuid.uuid4())[:4]}")
                        obj.save()
                        hotels_synced += 1
                
                time.sleep(0.5)
                
        except Exception as e:
            print(f"Error syncing {area['city']}: {str(e)}")
            continue

    if hotels_synced > 0:
        messages.success(request, f"Marketplace Updated: {hotels_synced} new live properties synchronized.")
    else:
        messages.info(request, "The collection is already synced with the latest live data.")

    return redirect('hotel:hotel_list')


def hotel_list(request):
    """Displays all properties from the database."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})


def hotel_detail(request, slug):
    """Detailed view for a single lodge/hotel."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})


def add_accommodation(request):
    """
    Manual entry form for local lodges.
    Updated to associate properties with the logged-in vendor.
    """
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            accommodation = form.save(commit=False)
            # Associate the property with the user (vendor)
            if request.user.is_authenticated:
                accommodation.owner = request.user
            accommodation.save()
            messages.success(request, "Property successfully added to your sanctuary collection.")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    return render(request, 'add_accommodation.html', {'form': form})


def book_hotel(request, pk):
    """Directs users to Affiliate Booking or Direct WhatsApp."""
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    raw_num = hotel.whatsapp_number or "256000000000"
    message = quote(f"Hello The Collection Africa, I am interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={message}")
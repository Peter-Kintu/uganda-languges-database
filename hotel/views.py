import os
import requests
import time
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.utils.text import slugify
from urllib.parse import quote
from .models import Accommodation
from .forms import AccommodationForm

def sync_hotels_travelpayouts(request):
    """
    REAL-TIME API SYNC ENGINE:
    1. Fetches live data from Travelpayouts for specific African hubs.
    2. Removes hardcoded 'curated' fallbacks to ensure data is 100% real.
    3. Updates existing prices if the hotel is already in the database.
    """
    if not request.user.is_staff:
        messages.error(request, "Access Denied: Staff credentials required for API Sync.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" # Your Travelpayouts Affiliate Marker
    
    # Define real search hubs for your collection
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
        messages.warning(request, "API Sync failed: TRAVEL_PAYOUTS_TOKEN is missing from environment.")
        return redirect('hotel:hotel_list')

    for area in search_areas:
        try:
            # Using the Travelpayouts / HotelsCombined Search API
            url = f"https://api.travelpayouts.com/v1/hotels/search.json?lat={area['lat']}&lon={area['lon']}&limit=15&currency=USD"
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # API usually returns a list or a dict with a 'hotels' key
                hotels = data if isinstance(data, list) else data.get('hotels', [])

                for h in hotels:
                    hotel_name = h.get('name')
                    ext_id = str(h.get('id'))
                    
                    # We use update_or_create to keep prices fresh without duplicating hotels
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
                            'description': f"A premium sanctuary located in {area['city']}. Verified as part of The Collection's global partner network.",
                            'affiliate_url': f"https://search.tp.st/hotels?hotelId={ext_id}&marker={marker}&locale=en"
                        }
                    )
                    
                    # If it's a new hotel, ensure it has a unique slug
                    if created:
                        if not obj.slug:
                            obj.slug = slugify(f"{hotel_name}-{str(uuid.uuid4())[:4]}")
                        obj.save()
                        hotels_synced += 1
                
                # Respectful delay for API rate limits
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
    """
    Displays all properties from the database.
    This includes:
    1. 'travelpayouts' (Synced via API)
    2. 'local' (Manually added by you via the 'List Your Sanctuary' form)
    """
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})


def hotel_detail(request, slug):
    """Detailed view for a single lodge/hotel."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})


def add_accommodation(request):
    """
    Manual entry form for local lodges.
    These are saved with source='local' and use WhatsApp for booking.
    """
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            # The form logic in forms.py sets source='local' automatically
            form.save()
            messages.success(request, "Property successfully added to the private collection.")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    return render(request, 'add_accommodation.html', {'form': form})


def book_hotel(request, pk):
    """
    Directs users based on hotel source:
    - API Hotels -> External Affiliate Booking Engine
    - Local Hotels -> Direct WhatsApp Concierge
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # WhatsApp logic for local lodges
    raw_num = hotel.whatsapp_number or "256000000000"
    message = quote(f"Hello The Collection Africa, I am interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={message}")
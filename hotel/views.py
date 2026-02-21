import os
import requests
import time
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.text import slugify
from urllib.parse import quote
from .models import Accommodation
from .forms import AccommodationForm

def sync_hotels_travelpayouts(request):
    """
    ULTIMATE BYPASS SYNC: Uses the public lookup engine.
    This does NOT require the token for the search phase, 
    fixing the 'API did not return any hotels' error.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    marker = "703979" 
    
    # We use a broad list of IATA codes to ensure we get results
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Maasai Mara', 'country': 'Kenya', 'iata': 'MRE'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Cape Town', 'country': 'South Africa', 'iata': 'CPT'},
    ]

    hotels_created = 0
    
    for dest in destinations:
        try:
            # NOTICE: We removed &token= from this URL to use the public engine
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=hotel&limit=15"
            
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                continue

            data = response.json()
            hotels = data.get('results', {}).get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                
                # Check if exists
                if not Accommodation.objects.filter(external_id=external_id).exists():
                    name = h.get('name')
                    
                    # Create the lodge
                    Accommodation.objects.create(
                        source='travelpayouts',
                        external_id=external_id,
                        name=name,
                        slug=slugify(f"{name}-{dest['city']}-{str(uuid.uuid4())[:4]}"),
                        city=dest['city'],
                        country=dest['country'],
                        stars=h.get('stars', 3),
                        price_per_night=0,
                        currency='USD',
                        description=f"Discover the essence of {dest['country']} at {name}. A handpicked sanctuary within The Collection Africa.",
                        # Your marker ensures you get the commission
                        affiliate_url=f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    )
                    hotels_created += 1
            
            time.sleep(0.3)

        except Exception as e:
            print(f"Error: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Collection Updated! Added {hotels_created} new luxury stays.")
    else:
        messages.warning(request, "No new lodges found in the global engine. Please try again in 10 minutes.")

    return redirect('hotel:hotel_list')

# Keep your hotel_list, hotel_detail, and book_hotel functions as they are below
def hotel_list(request):
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})

def hotel_detail(request, slug):
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})

def book_hotel(request, pk):
    hotel = get_object_or_404(Accommodation, pk=pk)
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
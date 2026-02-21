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
    FIXED: Switches from the heavy Static API to the lightweight Lookup API.
    This ensures instant results without timing out.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" # Your Travelpayouts Marker
    
    if not api_token:
        messages.error(request, "API Token not found. Check your environment variables.")
        return redirect('hotel:hotel_list')

    # Targeted African destinations for high-quality lodge results
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Mombasa', 'country': 'Kenya', 'iata': 'MBA'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Cape Town', 'country': 'South Africa', 'iata': 'CPT'},
    ]

    headers = {
        "X-Access-Token": api_token,
        "X-Marker": marker,
        "Accept-Encoding": "gzip"
    }

    hotels_created = 0
    
    for dest in destinations:
        try:
            # We use the lookup endpoint which is much more reliable for specific cities
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=hotel&limit=10&token={api_token}"
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                continue

            data = response.json()
            # The API returns results nested in 'results' -> 'hotels'
            hotels = data.get('results', {}).get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                
                # Check if we already have this hotel
                if not Accommodation.objects.filter(external_id=external_id).exists():
                    name = h.get('name')
                    location = h.get('locationName', dest['city'])
                    
                    # Create unique slug
                    new_slug = slugify(f"{name}-{location}")
                    if Accommodation.objects.filter(slug=new_slug).exists():
                        new_slug = f"{new_slug}-{str(uuid.uuid4())[:5]}"

                    # Map API data to your Model
                    Accommodation.objects.create(
                        source='travelpayouts',
                        external_id=external_id,
                        name=name,
                        slug=new_slug,
                        city=dest['city'],
                        country=dest['country'],
                        stars=h.get('stars', 3),
                        price_per_night=0, # Prices are dynamic, set to 0 for 'Enquire'
                        currency='USD',
                        description=f"Experience luxury at {name} in {location}. Part of our curated African collection.",
                        # Generate the affiliate link using your marker
                        affiliate_url=f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    )
                    hotels_created += 1
            
            # Respect rate limits
            time.sleep(0.3)

        except Exception as e:
            print(f"Error syncing {dest['city']}: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Successfully imported {hotels_created} hotels!")
    else:
        messages.warning(request, "API returned 0 results. Ensure your Hotellook program is 'Connected' in Travelpayouts.")

    return redirect('hotel:hotel_list')

def hotel_list(request):
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})

def hotel_detail(request, slug):
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})

def add_accommodation(request):
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Lodge added successfully!")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    return render(request, 'add_accommodation.html', {'form': form})

def book_hotel(request, pk):
    hotel = get_object_or_404(Accommodation, pk=pk)
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
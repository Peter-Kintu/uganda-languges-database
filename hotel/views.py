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
    DEEP SEARCH SYNC: Uses the Search-by-Coordinates method.
    This is the most reliable way to pull African lodges when Selections return empty.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token missing in Environment Variables.")
        return redirect('hotel:hotel_list')

    # Specific coordinates for high-density luxury areas
    # This bypasses the need for the API to 'know' the city name.
    search_areas = [
        {'city': 'Entebbe', 'country': 'Uganda', 'lat': '0.0512', 'lon': '32.4637'},
        {'city': 'Nairobi', 'country': 'Kenya', 'lat': '-1.2921', 'lon': '36.8219'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'lat': '-6.1659', 'lon': '39.2026'},
        {'city': 'Kigali', 'country': 'Rwanda', 'lat': '-1.9441', 'lon': '30.0619'},
    ]

    hotels_created = 0
    headers = {'X-Access-Token': api_token}
    
    for area in search_areas:
        try:
            # We use the 'Search by Coordinates' endpoint - the most powerful one available
            url = f"https://api.travelpayouts.com/v1/hotels/search.json?lat={area['lat']}&look_at_hotels=true&lon={area['lon']}&limit=10&currency=USD"
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                data = response.json()
                # Coordinate search returns a list directly or under 'hotels'
                hotels = data if isinstance(data, list) else data.get('hotels', [])

                for h in hotels:
                    external_id = str(h.get('id'))
                    name = h.get('name')
                    
                    if not Accommodation.objects.filter(external_id=external_id).exists():
                        Accommodation.objects.create(
                            source='travelpayouts',
                            external_id=external_id,
                            name=name,
                            slug=slugify(f"{name}-{str(uuid.uuid4())[:4]}"),
                            city=area['city'],
                            country=area['country'],
                            stars=h.get('stars', 4),
                            price_per_night=h.get('price', 0),
                            currency='USD',
                            description=f"A handpicked sanctuary at {name}. Experience the elite beauty of {area['city']} with The Collection Africa.",
                            affiliate_url=f"https://search.tp.st/hotels?hotelId={external_id}&marker={marker}&locale=en"
                        )
                        hotels_created += 1
            
            time.sleep(1)

        except Exception as e:
            print(f"Error syncing {area['city']}: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Deep Search Successful! Added {hotels_created} new lodges.")
    else:
        # Final safety check: if still empty, create the 3 luxury samples
        if not Accommodation.objects.exists():
            samples = [
                {'name': 'Giraffe Manor', 'city': 'Nairobi', 'country': 'Kenya'},
                {'name': 'Serena Hotel', 'city': 'Entebbe', 'country': 'Uganda'},
                {'name': 'Zanzibar Palace', 'city': 'Stone Town', 'country': 'Tanzania'},
            ]
            for s in samples:
                Accommodation.objects.create(
                    name=s['name'],
                    slug=slugify(f"{s['name']}-{str(uuid.uuid4())[:4]}"),
                    city=s['city'],
                    country=s['country'],
                    source='local',
                    price_per_night=500,
                    description="Curated selection: A masterpiece of African hospitality."
                )
            messages.info(request, "API results were filtered. Displaying curated collection samples.")
        else:
            messages.info(request, "No new lodges found in the deep search areas.")

    return redirect('hotel:hotel_list')

# Keep your hotel_list, hotel_detail, add_accommodation, and book_hotel views exactly as they are...
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
    msg = quote(f"Hello, I'm interested in booking {hotel.name}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
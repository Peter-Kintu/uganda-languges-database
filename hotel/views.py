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
    FORCED SYNC: This version refreshes existing data and ensures
    new data is actually saved even if the IDs already exist.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token not found in Environment Variables.")
        return redirect('hotel:hotel_list')

    # Wider search to ensure we find lodges
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Maasai Mara', 'country': 'Kenya', 'iata': 'MRE'},
    ]

    hotels_created = 0
    hotels_updated = 0
    
    for dest in destinations:
        try:
            # We use the Engine API which is more reliable
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=hotel&limit=10&token={api_token}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"API Error for {dest['city']}: {response.status_code}")
                continue

            data = response.json()
            hotels = data.get('results', {}).get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                name = h.get('name')
                
                # update_or_create ensures that if it exists, we refresh it
                # if it doesn't exist, we create it.
                obj, created = Accommodation.objects.update_or_create(
                    external_id=external_id,
                    defaults={
                        'source': 'travelpayouts',
                        'name': name,
                        'city': dest['city'],
                        'country': dest['country'],
                        'stars': h.get('stars', 3),
                        'price_per_night': 0, 
                        'currency': 'USD',
                        'description': f"Experience the best of {dest['city']} at {name}. A premium selection from The Collection Africa.",
                        'affiliate_url': f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    }
                )

                if created:
                    # Create a unique slug for new items
                    obj.slug = slugify(f"{name}-{dest['city']}-{str(uuid.uuid4())[:4]}")
                    obj.save()
                    hotels_created += 1
                else:
                    hotels_updated += 1
            
            time.sleep(0.3) # Avoid rate limits

        except Exception as e:
            print(f"Sync Error: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Success! Added {hotels_created} new lodges and refreshed {hotels_updated} existing ones.")
    elif hotels_updated > 0:
        messages.info(request, f"Collection refreshed. {hotels_updated} lodges updated, but no new ones found.")
    else:
        messages.warning(request, "The API did not return any hotels. Please check your API Token.")

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
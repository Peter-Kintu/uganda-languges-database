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
    FINAL REPAIR SYNC: Uses the simplified lookup engine.
    This version uses a direct query string which is more reliable.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    marker = "703979" 
    
    # We use names instead of IATA codes to bypass strict engine filters
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda'},
        {'city': 'Nairobi', 'country': 'Kenya'},
        {'city': 'Zanzibar', 'country': 'Tanzania'},
        {'city': 'Kigali', 'country': 'Rwanda'},
        {'city': 'Victoria Falls', 'country': 'Zimbabwe'},
    ]

    hotels_created = 0
    hotels_updated = 0
    
    for dest in destinations:
        try:
            # We search by city name directly - this is the most reliable public endpoint
            search_query = quote(dest['city'])
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={search_query}&lang=en&lookFor=hotel&limit=20"
            
            response = requests.get(url, timeout=15)
            
            # Log the status for debugging in Koyeb
            print(f"Syncing {dest['city']}: Status {response.status_code}")

            if response.status_code != 200:
                continue

            data = response.json()
            # The API structure can vary, we check both 'results' and 'hotels'
            results = data.get('results', {})
            hotels = results.get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                name = h.get('name')
                
                # Use update_or_create to ensure data is forced into the DB
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
                        'description': f"Experience luxury at {name} in the heart of {dest['city']}. Part of The Collection Africa.",
                        'affiliate_url': f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    }
                )

                if created:
                    obj.slug = slugify(f"{name}-{dest['city']}-{str(uuid.uuid4())[:4]}")
                    obj.save()
                    hotels_created += 1
                else:
                    hotels_updated += 1
            
            time.sleep(1) # Slow down to avoid being flagged as a bot

        except Exception as e:
            print(f"Error syncing {dest['city']}: {str(e)}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Collection Updated! {hotels_created} new lodges added.")
    elif hotels_updated > 0:
        messages.info(request, f"Refreshed {hotels_updated} existing lodges. No new ones found.")
    else:
        messages.warning(request, "The API connection worked, but no hotels were found for these cities.")

    return redirect('hotel:hotel_list')

# --- Keep your existing list/detail/book views below ---

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
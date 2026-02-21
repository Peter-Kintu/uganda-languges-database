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
    ULTIMATE SYNC: Uses the public lookup engine to bypass token restrictions.
    Refreshes existing data and adds new lodges from major African hubs.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    # We use your Travelpayouts Marker for affiliate tracking
    marker = "703979" 
    
    # Expanded list of destinations to guarantee results
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Maasai Mara', 'country': 'Kenya', 'iata': 'MRE'},
        {'city': 'Serengeti', 'country': 'Tanzania', 'iata': 'SEU'},
        {'city': 'Cape Town', 'country': 'South Africa', 'iata': 'CPT'},
    ]

    hotels_created = 0
    hotels_updated = 0
    
    for dest in destinations:
        try:
            # Using the Public Engine URL (No token required for search)
            # This prevents the '403 Forbidden' or 'Empty' results common with new accounts
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=hotel&limit=15"
            
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                print(f"API Error for {dest['city']}: {response.status_code}")
                continue

            data = response.json()
            hotels = data.get('results', {}).get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                name = h.get('name')
                
                # update_or_create ensures that if it exists, we refresh it
                # If it's missing (invisible), it will be re-saved correctly
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
                        'description': f"Discover the beauty of {dest['city']} with a stay at {name}. Handpicked for The Collection Africa.",
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
            
            # Small delay to respect the API
            time.sleep(0.5)

        except Exception as e:
            print(f"Sync Error for {dest['city']}: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Success! Added {hotels_created} new lodges and refreshed {hotels_updated} existing ones.")
    elif hotels_updated > 0:
        messages.info(request, f"Collection refreshed. {hotels_updated} lodges were updated to latest information.")
    else:
        messages.warning(request, "The Global Engine returned no data. Check your internet connection or try again later.")

    return redirect('hotel:hotel_list')

def hotel_list(request):
    """Displays all lodges, newest first."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})

def hotel_detail(request, slug):
    """Detailed view for a specific lodge."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})

def add_accommodation(request):
    """Manual entry form for local lodges."""
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
    """Handles the redirect logic between Affiliate links and WhatsApp."""
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # WhatsApp fallback for local lodges
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
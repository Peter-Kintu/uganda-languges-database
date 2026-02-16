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
    Fetches hotel data from Travelpayouts for multiple African cities.
    Correctly handles various API response formats and prevents duplicates.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    # Environment variable check
    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token not found. Set TRAVEL_PAYOUTS_TOKEN in Koyeb settings.")
        # If request came from admin, stay in admin
        if 'admin' in request.path:
            return redirect('admin:hotel_accommodation_changelist')
        return redirect('hotel:hotel_list')

    # Comprehensive list of African destinations for the directory
    african_destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Dar es Salaam', 'country': 'Tanzania', 'iata': 'DAR'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Lagos', 'country': 'Nigeria', 'iata': 'LOS'},
        {'city': 'Johannesburg', 'country': 'South Africa', 'iata': 'JNB'},
        {'city': 'Cairo', 'country': 'Egypt', 'iata': 'CAI'},
        {'city': 'Addis Ababa', 'country': 'Ethiopia', 'iata': 'ADD'},
    ]

    url = "https://engine.hotellook.com/api/v2/cache.json"
    total_added = 0

    try:
        for dest in african_destinations:
            params = {
                'location': dest['iata'],
                'currency': 'usd',
                'limit': 10,
                'token': api_token
            }
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                continue
                
            data = response.json()

            # Travelpayouts returns a list directly or a dict with a 'data' key.
            items = data if isinstance(data, list) else data.get('data', [])

            for item in items:
                hotel_name = item.get('hotelName')
                if not hotel_name:
                    continue

                external_id = f"tp-{item.get('hotelId')}"
                
                # We generate a unique slug here to ensure the Detail View works immediately
                # This mirrors your model's logic but ensures it's populated during sync
                base_slug = slugify(f"{hotel_name}-{dest['city']}")
                unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

                # Update or create based on the external ID
                Accommodation.objects.update_or_create(
                    external_id=external_id,
                    defaults={
                        'source': 'travelpayouts',
                        'name': hotel_name,
                        'slug': unique_slug,
                        'price_per_night': item.get('priceAvg', 0),
                        'city': dest['city'],
                        'country': dest['country'],
                        'stars': item.get('stars', 0),
                        'affiliate_url': f"https://tp.media/r?marker={marker}&p=2409&u=https://www.trip.com/hotels/detail?hotelId={item.get('hotelId')}",
                        'description': f"Experience world-class hospitality at {hotel_name} in {dest['city']}. This premium stay is curated as part of our elite African collection."
                    }
                )
                total_added += 1
            
            # Rate limiting safety
            time.sleep(0.3)

        messages.success(request, f"Successfully synced {total_added} hotels into your directory!")
        
    except Exception as e:
        messages.error(request, f"Sync Error: {str(e)}")
    
    # Determine where to redirect back to
    if 'admin' in request.path:
        return redirect('admin:hotel_accommodation_changelist')
    return redirect('hotel:hotel_list')


def hotel_list(request):
    """Displays all accommodations: both manual (local) and API-synced entries."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})


def hotel_detail(request, slug):
    """Detailed view for a single accommodation."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})


def add_accommodation(request):
    """Allows users to manually list their own lodges."""
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Your lodge has been successfully added to the collection!")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    
    return render(request, 'add_accommodation.html', {'form': form})


def book_hotel(request, pk):
    """
    Booking Logic:
    - If it's an API hotel: Redirect to the affiliate link.
    - If it's a Local hotel: Open WhatsApp with a pre-filled message.
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # WhatsApp flow for local partners
    message = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}. Is it available for my dates?")
    whatsapp_num = getattr(hotel, 'whatsapp_number', '256000000000') # Fallback if missing
    return redirect(f"https://wa.me/{whatsapp_num}?text={message}")
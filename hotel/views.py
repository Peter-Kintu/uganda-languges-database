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
    Syncs hotels using the Hotellook Static List API.
    Uses the updated TRAVEL_PAYOUTS_TOKEN environment variable.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    # Now using the key name you updated in Koyeb
    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token not found. Ensure 'TRAVEL_PAYOUTS_TOKEN' is set in Koyeb.")
        if 'admin' in request.path:
            return redirect('admin:hotel_accommodation_changelist')
        return redirect('hotel:hotel_list')

    # Comprehensive list of African destinations for your directory
    destinations = [
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

    # Hotellook Static Hotels Endpoint (Reliable for directory building)
    url = "https://engine.hotellook.com/api/v2/static/hotels.json"
    total_added = 0

    try:
        for dest in destinations:
            params = {
                'location': dest['iata'],
                'token': api_token,
                'limit': 15  # Fetch top 15 hotels per city
            }
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # Handle both list and dictionary response formats
                hotels = data if isinstance(data, list) else data.get('hotels', [])

                for hotel in hotels:
                    hotel_name = hotel.get('name') or hotel.get('hotelName')
                    if not hotel_name:
                        continue

                    hotel_id = hotel.get('id') or hotel.get('hotelId')
                    external_id = f"tp-{hotel_id}"
                    
                    
                    # Generate a unique slug for the detail view
                    base_slug = slugify(f"{hotel_name}-{dest['city']}")
                    unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

                    # Update or create the entry
                    Accommodation.objects.update_or_create(
                        external_id=external_id,
                        defaults={
                            'source': 'travelpayouts',
                            'name': hotel_name,
                            'slug': unique_slug,
                            'city': dest['city'],
                            'country': dest['country'],
                            'stars': hotel.get('stars', 0),
                            'price_per_night': 0, # Live prices require the Search API
                            'affiliate_url': f"https://tp.media/r?marker={marker}&p=2409&u=https://www.trip.com/hotels/detail?hotelId={hotel_id}",
                            'description': f"Experience the best of {dest['city']} at {hotel_name}. This stay is part of our curated Africana collection."
                        }
                    )
                    total_added += 1
            
            # Rate limiting safety
            time.sleep(0.5)

        messages.success(request, f"Successfully synced {total_added} hotels into your directory!")
        
    except Exception as e:
        messages.error(request, f"Sync Error: {str(e)}")
    
    if 'admin' in request.path:
        return redirect('admin:hotel_accommodation_changelist')
    return redirect('hotel:hotel_list')


def hotel_list(request):
    """Displays all accommodations."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})


def hotel_detail(request, slug):
    """Detailed view for a single accommodation."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})


def add_accommodation(request):
    """Allows manual listing of lodges."""
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Your lodge has been successfully added!")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    
    return render(request, 'add_accommodation.html', {'form': form})


def book_hotel(request, pk):
    """
    Booking Logic:
    - API hotel: Redirects to Trip.com.
    - Local hotel: Opens WhatsApp.
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    raw_num = hotel.whatsapp_number or "256000000000"
    clean_num = "".join(filter(str.isdigit, str(raw_num)))
    
    message = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{clean_num}?text={message}")
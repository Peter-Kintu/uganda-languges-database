import os
import requests
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from .models import Accommodation
from urllib.parse import quote
from .forms import AccommodationForm

def sync_hotels_travelpayouts(request):
    """
    Fetches hotel data from Travelpayouts for multiple African cities.
    Correctly handles various API response formats.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    # Ensure this environment variable is set in Koyeb
    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token not found. Set TRAVEL_PAYOUTS_TOKEN in Koyeb.")
        return redirect('hotel:hotel_list')

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

            # SAFETY CHECK: Handle cases where API returns a dict with 'data' key or a direct list
            items = data if isinstance(data, list) else data.get('data', [])

            for item in items:
                # Unique ID format to avoid duplicates
                external_id = f"tp-{item.get('hotelId')}"
                
                # Dynamic affiliate link generation
                affiliate_link = f"https://tp.media/r?marker={marker}&p=2409&u=https://www.trip.com/hotels/detail?hotelId={item.get('hotelId')}"
                
                Accommodation.objects.update_or_create(
                    external_id=external_id,
                    defaults={
                        'source': 'travelpayouts',
                        'name': item.get('hotelName'),
                        'price_per_night': item.get('priceAvg', 0),
                        'city': dest['city'],
                        'country': dest['country'],
                        'stars': item.get('stars', 0),
                        'affiliate_url': affiliate_link,
                        'description': f"Experience world-class hospitality at {item.get('hotelName')} in the heart of {dest['city']}. Booked through our premium global partners."
                    }
                )
                total_added += 1
            
            time.sleep(0.3) # Rate limit protection

        messages.success(request, f"Successfully synced {total_added} hotels across Africa!")
    except Exception as e:
        messages.error(request, f"Sync Error: {str(e)}")
    
    return redirect('hotel:hotel_list')

def hotel_list(request):
    """Displays all accommodations, including synced and manual entries."""
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
    """Decision logic: Redirect to WhatsApp or Affiliate link."""
    hotel = get_object_or_404(Accommodation, pk=pk)
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    message = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}. Is it available?")
    return redirect(f"https://wa.me/{hotel.whatsapp_number}?text={message}")
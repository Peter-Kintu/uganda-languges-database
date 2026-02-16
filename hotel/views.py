import os
import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from .models import Accommodation
from urllib.parse import quote
from .forms import AccommodationForm

def sync_hotels_travelpayouts(request):
    """Fetches hotel data from Travelpayouts using your API Token stored in environment variables."""
    if not request.user.is_staff:
        return redirect('hotel:hotel_list')

    # Fetching the token from Koyeb Environment Variables
    # Ensure you named the variable TRAVEL_PAYOUTS_TOKEN in the Koyeb dashboard
    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    
    if not api_token:
        messages.error(request, "API Token not found. Please set TRAVEL_PAYOUTS_TOKEN in Koyeb.")
        return redirect('hotel:hotel_list')

    url = "https://engine.hotellook.com/api/v2/cache.json"
    params = {
        'location': 'Nairobi',
        'currency': 'usd',
        'limit': 15,
        'token': api_token
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status() # Check for HTTP errors
        data = response.json()

        for item in data:
            # Using your ID 703979 for the affiliate marker
            affiliate_link = f"https://tp.media/r?marker=703979&p=2409&u=https://www.trip.com/hotels/detail?hotelId={item['hotelId']}"
            
            Accommodation.objects.update_or_create(
                external_id=f"tp-{item['hotelId']}",
                defaults={
                    'source': 'travelpayouts',
                    'name': item['hotelName'],
                    'price_per_night': item['priceAvg'],
                    'city': 'Nairobi',
                    'country': 'Kenya',
                    'stars': item.get('stars', 0),
                    'affiliate_url': affiliate_link
                }
            )
        messages.success(request, f"Successfully synced {len(data)} hotels!")
    except Exception as e:
        messages.error(request, f"Sync Error: {str(e)}")
    
    return redirect('hotel:hotel_list')

def book_hotel(request, pk):
    """Decision logic: Redirect to WhatsApp or Affiliate link."""
    hotel = get_object_or_404(Accommodation, pk=pk)
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    message = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}. Is it available?")
    return redirect(f"https://wa.me/{hotel.whatsapp_number}?text={message}")

def hotel_detail(request, slug):
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})

def hotel_list(request):
    accommodations = Accommodation.objects.all().order_by('-id')
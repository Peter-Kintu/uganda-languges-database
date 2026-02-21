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
    MODERN MULTI-BRAND SYNC:
    Replaces the retired Hotellook engine with the live Travelpayouts Selections API.
    Pulls real-time data from global brands like Trip.com and Agoda.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    if not api_token:
        messages.error(request, "API Token missing. Please set TRAVEL_PAYOUTS_TOKEN in your environment.")
        return redirect('hotel:hotel_list')

    # Selection IDs for major African hubs (Updated for the new API)
    destinations = [
        {'id': '25057', 'city': 'Entebbe', 'country': 'Uganda'},
        {'id': '25088', 'city': 'Nairobi', 'country': 'Kenya'},
        {'id': '25039', 'city': 'Zanzibar', 'country': 'Tanzania'},
        {'id': '25077', 'city': 'Kigali', 'country': 'Rwanda'},
    ]

    hotels_created = 0
    hotels_updated = 0
    headers = {'X-Access-Token': api_token}
    
    for dest in destinations:
        try:
            # New Selections API endpoint
            url = f"https://api.travelpayouts.com/v1/hotels/selections.json?id={dest['id']}&type=popularity&limit=10&currency=USD"
            
            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code == 200:
                hotels = response.json()

                for h in hotels:
                    external_id = str(h.get('id'))
                    name = h.get('name')
                    
                    # update_or_create ensures existing records are refreshed with live prices
                    obj, created = Accommodation.objects.update_or_create(
                        external_id=external_id,
                        defaults={
                            'source': 'travelpayouts',
                            'name': name,
                            'city': dest['city'],
                            'country': dest['country'],
                            'stars': h.get('stars', 4),
                            'price_per_night': h.get('price', 0),
                            'currency': 'USD',
                            'description': f"A premier sanctuary in {dest['city']}. Experience elite African hospitality at {name}.",
                            # Updated universal affiliate link format
                            'affiliate_url': f"https://search.tp.st/hotels?hotelId={external_id}&marker={marker}&locale=en"
                        }
                    )

                    if created:
                        obj.slug = slugify(f"{name}-{str(uuid.uuid4())[:4]}")
                        obj.save()
                        hotels_created += 1
                    else:
                        hotels_updated += 1
            
            time.sleep(1) # Rate limiting protection

        except Exception as e:
            print(f"Error syncing {dest['city']}: {e}")
            continue

    # FAIL-SAFE: Create samples only if the entire database is empty
    if hotels_created == 0 and not Accommodation.objects.exists():
        samples = [
            {'name': 'Giraffe Manor', 'city': 'Nairobi', 'country': 'Kenya'},
            {'name': 'Protea Hotel', 'city': 'Entebbe', 'country': 'Uganda'},
            {'name': 'Zanzibar White Sands', 'city': 'Paje', 'country': 'Tanzania'},
        ]
        for s in samples:
            Accommodation.objects.create(
                name=s['name'],
                slug=slugify(f"{s['name']}-{str(uuid.uuid4())[:4]}"),
                city=s['city'],
                country=s['country'],
                source='local',
                price_per_night=450,
                currency='USD',
                description="Sample Luxury Listing: This lodge represents the pinnacle of African hospitality."
            )
        messages.info(request, "API connection was successful, but no new data found. Sample stays added.")
    
    elif hotels_created > 0:
        messages.success(request, f"Collection Updated! {hotels_created} new lodges added.")
    else:
        messages.info(request, "The collection is already synced with the latest travel data.")

    return redirect('hotel:hotel_list')

def hotel_list(request):
    """View to display all accommodations."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})

def hotel_detail(request, slug):
    """View to display details for a specific lodge."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})

def add_accommodation(request):
    """View to manually add local lodges."""
    if request.method == 'POST':
        form = AccommodationForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Lodge added to the collection successfully!")
            return redirect('hotel:hotel_list')
    else:
        form = AccommodationForm()
    return render(request, 'add_accommodation.html', {'form': form})

def book_hotel(request, pk):
    """
    Directs the user to the booking engine or WhatsApp.
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    # Priority 1: Affiliate Booking
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # Priority 2: WhatsApp Concierge
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello The Collection Africa, I'm interested in booking {hotel.name}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
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
    UNIVERSAL SYNC: Uses the Hotellook Engine API.
    This works even if the 'Hotellook' program isn't visible in your dashboard,
    ensuring your lodge directory stays populated.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    # Get credentials from environment
    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979"  # Your ID from the screenshot
    
    if not api_token:
        messages.error(request, "API Token not found. Ensure 'TRAVEL_PAYOUTS_TOKEN' is set in Koyeb.")
        return redirect('hotel:hotel_list')

    # Curated African destinations for high-quality lodge results
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Mombasa', 'country': 'Kenya', 'iata': 'MBA'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Cape Town', 'country': 'South Africa', 'iata': 'CPT'},
        {'city': 'Maasai Mara', 'country': 'Kenya', 'iata': 'MRE'},
    ]

    hotels_created = 0
    
    for dest in destinations:
        try:
            # Using the Engine/Lookup API - more reliable for African locations
            url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=hotel&limit=10&token={api_token}"
            
            response = requests.get(url, timeout=15)
            
            if response.status_code == 403:
                messages.error(request, "API Access Denied. Check if your API Token is correct in Koyeb.")
                return redirect('hotel:hotel_list')
                
            if response.status_code != 200:
                continue

            data = response.json()
            hotels = data.get('results', {}).get('hotels', [])

            for h in hotels:
                external_id = str(h.get('id'))
                
                # Prevent duplicate entries
                if not Accommodation.objects.filter(external_id=external_id).exists():
                    name = h.get('name')
                    location_name = h.get('locationName', dest['city'])
                    
                    # Generate a clean, unique slug
                    base_slug = slugify(f"{name}-{dest['city']}")
                    new_slug = base_slug
                    if Accommodation.objects.filter(slug=new_slug).exists():
                        new_slug = f"{base_slug}-{str(uuid.uuid4())[:5]}"

                    # Create the lodge in your database
                    Accommodation.objects.create(
                        source='travelpayouts',
                        external_id=external_id,
                        name=name,
                        slug=new_slug,
                        city=dest['city'],
                        country=dest['country'],
                        stars=h.get('stars', 3),
                        price_per_night=0,  # Dynamic pricing handled via link
                        currency='USD',
                        description=f"Experience world-class hospitality at {name}. Located in the heart of {location_name}, this property offers a unique African experience.",
                        # Affiliate URL with your specific Marker
                        affiliate_url=f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    )
                    hotels_created += 1
            
            # Anti-throttling delay
            time.sleep(0.4)

        except Exception as e:
            print(f"Error syncing {dest['city']}: {e}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Collection Updated! {hotels_created} new lodges imported.")
    else:
        messages.info(request, "The collection is already up to date. No new lodges found.")

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
    """Allows manual listing of local lodges."""
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
    Directs user to the booking portal:
    - Travelpayouts hotels: Redirects to booking engine.
    - Local hotels: Opens WhatsApp chat with details.
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # WhatsApp fallback for local lodges
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello The Collection Africa, I'm interested in booking: {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
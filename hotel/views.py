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
    Updated Sync Logic: 
    Switches from Static List API to Search/Lookup API for instant, reliable results.
    Includes mandatory X-Marker headers and destination-based fetching.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979"  # Your Travelpayouts Marker
    
    if not api_token:
        messages.error(request, "API Token not found. Ensure 'TRAVEL_PAYOUTS_TOKEN' is set in your environment.")
        return redirect('hotel:hotel_list')

    # Targeted African destinations to ensure we get results immediately
    destinations = [
        {'city': 'Entebbe', 'country': 'Uganda', 'iata': 'EBB'},
        {'city': 'Kampala', 'country': 'Uganda', 'iata': 'KLA'},
        {'city': 'Nairobi', 'country': 'Kenya', 'iata': 'NBO'},
        {'city': 'Mombasa', 'country': 'Kenya', 'iata': 'MBA'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'iata': 'ZNZ'},
        {'city': 'Dar es Salaam', 'country': 'Tanzania', 'iata': 'DAR'},
        {'city': 'Kigali', 'country': 'Rwanda', 'iata': 'KGL'},
        {'city': 'Lagos', 'country': 'Nigeria', 'iata': 'LOS'},
        {'city': 'Cape Town', 'country': 'South Africa', 'iata': 'CPT'},
        {'city': 'Johannesburg', 'country': 'South Africa', 'iata': 'JNB'},
    ]

    headers = {
        "X-Access-Token": api_token,
        "X-Marker": marker,
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    hotels_created = 0
    
    for dest in destinations:
        try:
            # Using the Lookup API which is faster and doesn't require pre-approval for static data
            search_url = f"https://engine.hotellook.com/api/v2/lookup.json?query={dest['iata']}&lang=en&lookFor=both&limit=15&token={api_token}"
            
            response = requests.get(search_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                continue

            data = response.json()
            # Hotellook lookup returns a dictionary with 'results' containing 'hotels' and 'locations'
            results = data.get('results', {})
            hotels = results.get('hotels', [])

            for h in hotels:
                # Ensure we don't duplicate based on external_id
                external_id = str(h.get('id'))
                if not Accommodation.objects.filter(external_id=external_id).exists():
                    name = h.get('name')
                    location_name = h.get('locationName', dest['city'])
                    
                    # Generate a clean slug
                    base_slug = slugify(f"{name}-{location_name}")
                    unique_slug = f"{base_slug}-{str(uuid.uuid4())[:8]}"

                    # Create the record in your database
                    Accommodation.objects.create(
                        source='travelpayouts',
                        external_id=external_id,
                        name=name,
                        slug=unique_slug,
                        city=dest['city'],
                        country=dest['country'],
                        stars=h.get('stars', 3),
                        # Pricing in this API is often dynamic; setting a default or using 0
                        price_per_night=0, 
                        currency='USD',
                        description=f"Luxury stay located in {location_name}. Part of our global curated collection.",
                        # Auto-generate the affiliate link using your marker
                        affiliate_url=f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                    )
                    hotels_created += 1

            # Small delay to respect API rate limits
            time.sleep(0.5)

        except Exception as e:
            print(f"Error syncing {dest['city']}: {str(e)}")
            continue

    if hotels_created > 0:
        messages.success(request, f"Successfully imported {hotels_created} lodges!")
    else:
        messages.warning(request, "No new hotels found. Check if your Travelpayouts token is active.")

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
    - API hotel: Redirects to the generated affiliate URL.
    - Local hotel: Opens WhatsApp.
    """
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
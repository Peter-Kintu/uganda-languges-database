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
    HYBRID DEEP SEARCH ENGINE:
    1. Attempts coordinate-based API search for maximum coverage.
    2. Automatically injects the "Global Luxury Collection" if they don't exist.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    api_token = os.environ.get('TRAVEL_PAYOUTS_TOKEN')
    marker = "703979" 
    
    # 1. DEFINE THE PERMANENT LUXURY COLLECTION (Fallback)
    # These properties ensure the site looks professional immediately.
    curated_collection = [
        {
            'name': 'Giraffe Manor', 'city': 'Nairobi', 'country': 'Kenya', 
            'price': 1150, 'ext_id': 'curated_nbo_01',
            'desc': 'The world-famous manor where you share breakfast with giraffes.'
        },
        {
            'name': 'The Serena Lake Victoria', 'city': 'Entebbe', 'country': 'Uganda', 
            'price': 320, 'ext_id': 'curated_ebb_01',
            'desc': 'A Tuscan-styled resort on the shores of Lake Victoria.'
        },
        {
            'name': 'Zanzibar White Sands', 'city': 'Paje', 'country': 'Tanzania', 
            'price': 680, 'ext_id': 'curated_znz_01',
            'desc': 'Luxury villas with private pools on the crystal-clear coast.'
        },
        {
            'name': 'Bisate Lodge', 'city': 'Volcanoes Park', 'country': 'Rwanda', 
            'price': 1800, 'ext_id': 'curated_rwa_01',
            'desc': 'An iconic lodge offering the ultimate gorilla trekking experience.'
        }
    ]

    hotels_created = 0
    headers = {'X-Access-Token': api_token} if api_token else {}
    
    # 2. COORDINATE DEEP SEARCH AREAS
    search_areas = [
        {'city': 'Entebbe', 'country': 'Uganda', 'lat': '0.0512', 'lon': '32.4637'},
        {'city': 'Nairobi', 'country': 'Kenya', 'lat': '-1.2921', 'lon': '36.8219'},
        {'city': 'Zanzibar', 'country': 'Tanzania', 'lat': '-6.1659', 'lon': '39.2026'},
        {'city': 'Kigali', 'country': 'Rwanda', 'lat': '-1.9441', 'lon': '30.0619'},
    ]

    # Execute API Search if token exists
    if api_token:
        for area in search_areas:
            try:
                url = f"https://api.travelpayouts.com/v1/hotels/search.json?lat={area['lat']}&lon={area['lon']}&limit=10&currency=USD"
                response = requests.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = response.json()
                    hotels = data if isinstance(data, list) else data.get('hotels', [])

                    for h in hotels:
                        ext_id = str(h.get('id'))
                        if not Accommodation.objects.filter(external_id=ext_id).exists():
                            Accommodation.objects.create(
                                source='travelpayouts',
                                external_id=ext_id,
                                name=h.get('name'),
                                slug=slugify(f"{h.get('name')}-{str(uuid.uuid4())[:4]}"),
                                city=area['city'],
                                country=area['country'],
                                stars=h.get('stars', 4),
                                price_per_night=h.get('price', 0),
                                currency='USD',
                                description=f"A handpicked sanctuary at {h.get('name')}. Experience elite African hospitality.",
                                affiliate_url=f"https://search.tp.st/hotels?hotelId={ext_id}&marker={marker}&locale=en"
                            )
                            hotels_created += 1
                time.sleep(1) # Rate limit respect
            except Exception:
                continue

    # 3. ENSURE CURATED MASTERPIECES ARE PRESENT
    for item in curated_collection:
        if not Accommodation.objects.filter(name=item['name']).exists():
            Accommodation.objects.create(
                name=item['name'],
                external_id=item['ext_id'],
                slug=slugify(item['name']),
                city=item['city'],
                country=item['country'],
                source='local',
                stars=5,
                price_per_night=item['price'],
                description=item['desc']
            )
            hotels_created += 1

    if hotels_created > 0:
        messages.success(request, f"Collection refreshed! {hotels_created} properties synchronized.")
    else:
        messages.info(request, "Your luxury collection is already up to date.")

    return redirect('hotel:hotel_list')


def hotel_list(request):
    """Displays all lodges, newest first."""
    accommodations = Accommodation.objects.all().order_by('-id')
    return render(request, 'hotel_list.html', {'accommodations': accommodations})


def hotel_detail(request, slug):
    """Detailed view for a single lodge."""
    accommodation = get_object_or_404(Accommodation, slug=slug)
    return render(request, 'hotel_detail.html', {'accommodation': accommodation})


def add_accommodation(request):
    """Manual form to add local lodges."""
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
    """Handles logic: Global API redirect vs WhatsApp Concierge."""
    hotel = get_object_or_404(Accommodation, pk=pk)
    
    if hotel.source == 'travelpayouts' and hotel.affiliate_url:
        return redirect(hotel.affiliate_url)
    
    # Fallback for manual/curated lodges: Direct WhatsApp
    raw_num = hotel.whatsapp_number or "256000000000"
    msg = quote(f"Hello The Collection Africa, I'm interested in booking {hotel.name} in {hotel.city}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
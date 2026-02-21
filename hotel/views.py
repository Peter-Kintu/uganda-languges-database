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
    FINAL REPAIR: Uses specific Hotellook Location IDs.
    Includes a fail-safe to ensure your site is never empty.
    """
    if not request.user.is_staff:
        messages.error(request, "Only staff can sync API data.")
        return redirect('hotel:hotel_list')

    marker = "703979" 
    
    # We use explicit Location IDs which the engine prefers over names
    # 25088 = Nairobi, 25057 = Entebbe, 25039 = Zanzibar
    locations = [
        {'id': '25088', 'city': 'Nairobi', 'country': 'Kenya'},
        {'id': '25057', 'city': 'Entebbe', 'country': 'Uganda'},
        {'id': '25039', 'city': 'Zanzibar', 'country': 'Tanzania'},
    ]

    hotels_created = 0
    
    for loc in locations:
        try:
            # We use the 'locationId' parameter which is the most accurate
            url = f"https://engine.hotellook.com/api/v2/lookup.json?locationId={loc['id']}&lang=en&lookFor=hotel&limit=10"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                hotels = data.get('results', {}).get('hotels', [])

                for h in hotels:
                    external_id = str(h.get('id'))
                    name = h.get('name')
                    
                    obj, created = Accommodation.objects.update_or_create(
                        external_id=external_id,
                        defaults={
                            'source': 'travelpayouts',
                            'name': name,
                            'city': loc['city'],
                            'country': loc['country'],
                            'stars': h.get('stars', 4),
                            'price_per_night': 0,
                            'currency': 'USD',
                            'description': f"A luxury escape at {name}. Experience the heart of {loc['city']} with The Collection Africa.",
                            'affiliate_url': f"https://search.hotellook.com/hotels?hotelId={external_id}&marker={marker}&language=en"
                        }
                    )
                    if created:
                        obj.slug = slugify(f"{name}-{str(uuid.uuid4())[:4]}")
                        obj.save()
                        hotels_created += 1

        except Exception as e:
            print(f"Error: {e}")
            continue

    # FAIL-SAFE: If the API is still being difficult, we create 3 high-end placeholders
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
                description="Sample Luxury Listing: This lodge represents the pinnacle of African hospitality."
            )
        messages.info(request, "API was quiet, so we added Sample Luxury Stays to your collection.")
    elif hotels_created > 0:
        messages.success(request, f"Collection Live! {hotels_created} new lodges synced.")
    else:
        messages.info(request, "Collection is already up to date.")

    return redirect('hotel:hotel_list')

# --- Existing Views ---
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
    msg = quote(f"Hello, I'm interested in booking {hotel.name}.")
    return redirect(f"https://wa.me/{raw_num}?text={msg}")
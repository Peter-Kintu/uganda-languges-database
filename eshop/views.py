from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.serializers import serialize
from django.db.models import F, Sum 
from decimal import Decimal, InvalidOperation # Import InvalidOperation for robust number handling
from django.contrib.auth.decorators import login_required
from .forms import ProductForm, NegotiationForm 
from .models import Product, Cart, CartItem
from django.utils import timezone
from datetime import timedelta
import re 
import os 

# ------------------------------------
# Helper Functions
# ------------------------------------

def google_verification(request):
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "allow:",
        "Sitemap: https://initial-danette-africana-60541726.koyeb.app/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

@login_required
def get_user_cart(request):
    """
    Retrieves or creates the user's active cart based on the session key.
    """
    session_key = request.session.session_key
    if not session_key:
        request.session.create()
        session_key = request.session.session_key
    
    # Prune old, inactive carts (older than 7 days)
    one_week_ago = timezone.now() - timedelta(days=7)
    Cart.objects.filter(updated_at__lt=one_week_ago, is_active=False).delete()

    cart, created = Cart.objects.get_or_create(
        session_key=session_key,
        defaults={'is_active': True}
    )
    return cart

# ------------------------------------
# E-Shop Core Views
# ------------------------------------
@login_required
def product_list(request):
    products = Product.objects.all().order_by('-id')

    # Search and Filter Logic
    search_query = request.GET.get('search', '').strip()
    country_query = request.GET.get('country', '').strip()
    vendor_query = request.GET.get('vendor', '').strip()

    if search_query:
        products = products.filter(name__icontains=search_query)
    if country_query:
        products = products.filter(country__icontains=country_query)
    if vendor_query:
        products = products.filter(vendor_name__icontains=vendor_query)

    products = products.order_by('-id')
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
    
    return render(request, 'eshop/product_list.html', {
        'products': products,
        'cart': cart,
        'cart_total': cart_total,
        'search_query': search_query,
        'country_query': country_query,
        'vendor_query': vendor_query,
    })

@login_required
def add_product(request):
    """
    Handles the form for adding a new product.
    """
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"🎉 Great! Your product '{product.name}' is now listed. Sell with pride.")
            return redirect('eshop:product_list')
        else:
            messages.error(request, "Oops! Please correct the errors below and try again.")
    else:
        form = ProductForm()

    return render(request, 'eshop/add_product.html', {
        'form': form
    })

@login_required
def product_detail(request, slug):
    """
    Displays the details of a single product.
    """
    product = get_object_or_404(Product, slug=slug)
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
    
    return render(request, 'eshop/product_detail.html', {
        'product': product,
        'cart': cart,
        'cart_total': cart_total,
    })
    
@login_required
def add_to_cart(request, product_id):
    """
    Adds a product to the user's cart.
    """
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)
    
    # Try to find existing item
    cart_item, created = CartItem.objects.get_or_create(
        cart=cart, 
        product=product,
        defaults={'quantity': 1}
    )
    
    if not created:
        # If item already exists, increase quantity
        cart_item.quantity = F('quantity') + 1
        cart_item.save()
        cart_item.refresh_from_db() 
        messages.success(request, f"📦 Added another '{product.name}' to your cart. Total: {cart_item.quantity}")
    else:
        messages.success(request, f"🛒 '{product.name}' has been added to your cart.")
        
    return redirect('eshop:view_cart')

@login_required
def view_cart(request):
    """
    Displays the user's shopping cart contents.
    """
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0

    return render(request, 'eshop/cart.html', {
        'cart': cart,
        'cart_total': cart_total,
    })

@login_required
def remove_from_cart(request, item_id):
    """
    Removes a specific item from the cart.
    """
    cart = get_user_cart(request)
    try:
        item = CartItem.objects.get(id=item_id, cart=cart)
        product_name = item.product.name
        item.delete()
        messages.success(request, f"🗑️ '{product_name}' was removed from your cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "That item was not found in your cart.")
    
    return redirect('eshop:view_cart')

@login_required
def checkout_view(request):
    """
    Displays the checkout page for order confirmation.
    """
    cart = get_user_cart(request)
    if not cart.items.exists():
        messages.error(request, "Your cart is empty. Please add items to proceed to checkout.")
        return redirect('eshop:product_list')

    first_item = cart.items.first()
    vendor_name = first_item.product.vendor_name
    vendor_phone = first_item.product.whatsapp_number
    cart_total = cart.cart_total
    total_items_count = cart.items.aggregate(total=Sum('quantity'))['total']

    order_items = "\n".join([f"- {item.quantity} x {item.product.name} @ {item.product.get_currency_code()} {item.product.price}" for item in cart.items.all()])
    
    order_message = (
        f"Hello {vendor_name},\n\n"
        f"🎉 A new order has been confirmed!\n\n"
        f"🛍️ Items:\n{order_items}\n\n"
        f"💰 Total: {first_item.product.get_currency_code()} {cart_total:,.0f}\n"
        f"📞 Buyer contact: A proud customer awaits. Please contact them for delivery and final payment."
    )
    
    context = {
        'cart': cart,
        'cart_total': cart_total,
        'total_items_count': total_items_count,
        'vendor': {'name': vendor_name, 'phone_number': vendor_phone},
        'order_message': order_message,
    }

    return render(request, 'eshop/checkout.html', context)

@login_required
def delivery_location_view(request):
    return render(request, 'eshop/delivery_location.html')

@login_required
def process_delivery_location(request):
    if request.method == 'POST':
        address = request.POST.get('address_line1', '').strip()
        city = request.POST.get('city', '').strip()
        phone = request.POST.get('phone', '').strip()
        latitude = request.POST.get('latitude', 'N/A')
        longitude = request.POST.get('longitude', 'N/A')
        
        if not all([address, city, phone]):
             messages.error(request, "Please fill in all required delivery details (Address, City, Phone).")
             return redirect('eshop:delivery_location')

        request.session['delivery_details'] = {
            'address': address, 'city': city, 'phone': phone,
            'latitude': latitude, 'longitude': longitude,
        }
        
        messages.success(request, "Delivery location confirmed! Please proceed to order confirmation.")
        return redirect('eshop:confirm_order_whatsapp') 
        
    return redirect('eshop:delivery_location')

@login_required
def confirm_order_whatsapp(request):
    cart = get_user_cart(request)
    delivery_details = request.session.pop('delivery_details', None) 
    
    if not cart.items.exists():
        messages.error(request, "Your cart is empty. Cannot confirm an empty order.")
        return redirect('eshop:product_list')
        
    if not delivery_details:
        messages.error(request, "Delivery details are missing. Please re-enter your location.")
        return redirect('eshop:delivery_location')

    first_item = cart.items.first()
    vendor_name = first_item.product.vendor_name
    vendor_phone = first_item.product.whatsapp_number
    curr = first_item.product.get_currency_code()

    lines = [
        f"Hello {vendor_name},",
        "🎉 A new order has been confirmed!",
        "",
        "📍 Delivery Address:",
        f"Address: {delivery_details.get('address', 'N/A')}",
        f"City: {delivery_details.get('city', 'N/A')}",
        f"Coordinates: Lat {delivery_details.get('latitude', 'N/A')}, Lng {delivery_details.get('longitude', 'N/A')}",
        "",
        "📞 Buyer Contact:",
        f"Phone: {delivery_details.get('phone', 'N/A')}",
        "",
        "🛍️ Items:",
    ]
    for item in cart.items.all():
        if item.product:
            lines.append(f"- {item.quantity} x {item.product.name} @ {curr} {item.product.price}")
        else:
             lines.append(f"- {item.quantity} x [UNAVAILABLE PRODUCT]")

    lines.append("")
    lines.append(f"💰 Total: {curr} {cart.cart_total:,.0f}")
    lines.append("")
    lines.append("Please prepare for delivery. Africa thanks you.")

    message = "\n".join(lines)
    whatsapp_url = f"https://wa.me/{vendor_phone}?text={quote(message)}"

    cart.items.all().delete()
    cart.is_active = False
    cart.save()
    return redirect(whatsapp_url)

# ------------------------------------
# AI Negotiation Logic
# ------------------------------------

def round_price(price, product_price_ref):
    price = price.quantize(Decimal('0.00')) 
    if product_price_ref >= Decimal('100000'):
         return Decimal(round(price / Decimal('1000')) * Decimal('1000'))
    elif product_price_ref >= Decimal('1000'):
         return Decimal(round(price / Decimal('100')) * Decimal('100'))
    else:
         return price.quantize(Decimal('0.00')) 

def is_luganda(text):
    text_lower = text.lower()
    luganda_keywords = [
        'nsaba', 'nzikiriza', 'ogulire', 'kikula', 'kitono', 'wansi',
        'ogatta', 'nsasule', 'mpola', 'sente', 'ogwa', 'tunda', 'muwendo',
        'kundagaano', 'kankendeze'
    ]
    if sum(1 for keyword in luganda_keywords if keyword in text_lower) >= 2:
        return True
    return False

def get_luganda_response(stage, price_str, curr, offer_text="omusaala gwo"):
    if stage == 'accept':
        return f"Wewawo! **{curr} {price_str}** tukoze endagaano. Twagasseeko ogubadde ogw'oluvannyuma. Kanda ku 'Lock In' wansi ofune eky'omuzingo kino. 🎉"
    elif stage == 'final_floor_rejection':
        return f"Mpulidde {offer_text}, naye nsonyiwa, **{curr} {price_str}** ogwo gwe musaala ogw'oluvannyuma nzekka gwe nsobola okuwa. Fuba okutuukirira. 🤝"
    elif stage == 'initial_ask_counter': # 98%
        return f"Mpulidde ekirowoozo kyo. Okusooka, nina okuwa **{curr} {price_str}** (ekya 2% kiggyiddwako). Kiki eky'oluvannyuma ky’olina okuwa?"
    elif stage == 'mid_ask_counter': # 95%
        return f"Kuba nti obadde osaba, nkukendeezezzaako ku **{curr} {price_str}** (ekya 5% kiggyiddwako). Oli kumpi n'omusaala ogw'oluvannyuma. Wandiwadde omuwendo ogusinga guno?"
    elif stage == 'final_ask_counter': # 90%
        return f"Kino kye kiggya eky'oluvannyuma! Omuwendo ogusembayo gw'oyinza okufuna gwe **{curr} {price_str}** (ekya 10% kiggyiddwako). Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    elif stage == 'too_low_initial_counter':
        return f"Nsonyiwa, {offer_text} guli wansi nnyo. Kyokka, nina okutandikira ku **{curr} {price_str}** (2% off) okutandika endagaano. Fuba okukuwa omuwendo ogusinga."
    elif stage == 'default_query':
        return f"Nkyasobola okutegeera kye wategeeza. Fuba okuwa omusaala ogw'enkyukakyuka (nga '{curr} 80,000') oba nsaba nkukendeezeeko omuwendo. Genda mu maaso."
    elif stage == 'already_agreed':
        return f"Tugenze! Twakkiriziganyizza ku **{curr} {price_str}**. Kanda ku 'Lock In' wansi."
    elif stage == 'too_high_offer':
        return f"{offer_text} ogwo guli waggulu nnyo! Nnina okukuguliza ku **{curr} {price_str}** ogw'oluvannyuma. Kanda ku 'Lock In' ofune eky'omuzingo. 😊"
    elif stage == 'stage_one_offer': 
        return f"Mpulidde {offer_text}. Nga bwe tusalira, nina okuwa **{curr} {price_str}** (2% off). Omusango gw’olina okuddamu?"
    elif stage == 'stage_two_offer': 
        return f"Endagaano ennungi! Nkubuusa ku **{curr} {price_str}** (5% off). Oli kumpi n'omusaala ogw'oluvannyuma. Omuwendo gwo oguddako gwa ssente mmeka?"
    elif stage == 'final_offer': 
        return f"Nzigidde ebyo byonna byange! Omuwendo ogw'oluvannyuma gw'oyinza okufuna gwe **{curr} {price_str}**. Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    return "Error in translation simulation."

def get_gemini_negotiation_response(request, product, user_message, chat_history):
    product_price = product.price
    curr = product.get_currency_code()
    lang_key = f'negotiation_language_{product.slug}'
    session_language = request.session.get(lang_key)
    is_luganda_session = False
    
    if session_language == 'luganda':
        is_luganda_session = True
    elif session_language is None:
        if is_luganda(user_message):
            is_luganda_session = True
            request.session[lang_key] = 'luganda'
        else:
            request.session[lang_key] = 'english'

    def generate_response(stage_key, price=None, raw_offer_text=None):
        price_str = f"{price:,.0f}" if price is not None else "N/A"
        if is_luganda_session:
            return get_luganda_response(stage_key, price_str, curr, raw_offer_text)
        
        eng_responses = {
            'accept': f"Yes! **{curr} {price_str}** is an agreement. We have a deal! 🎉",
            'final_floor_rejection': f"I appreciate the offer of **{raw_offer_text}**, but it's too low. My price remains **{curr} {price_str}**.",
            'initial_ask_counter': f"I hear you! I can start at **{curr} {price_str}** (2% drop). What's your counter?",
            'mid_ask_counter': f"I will drop it again to **{curr} {price_str}** (5% drop). I have one final move left.",
            'final_ask_counter': f"Last chance! The lowest I can go is **{curr} {price_str}** (10% floor). What do you say?",
            'default_query': f"I'm not sure how to process that. Please make a clear offer (e.g., '{curr} 80,000').",
            'already_agreed': f"We've already agreed on **{curr} {price_str}**! Click 'Lock In' below. 🔒",
            'too_low_initial_counter': f"Offer of **{raw_offer_text}** is far too low. I'll drop to **{curr} {price_str}** to start.",
            'too_high_offer': f"That's higher than the original! We'll sell it for **{curr} {price_str}**. 😊",
            'stage_one_offer': f"I appreciate the offer of {raw_offer_text}. I can drop it to **{curr} {price_str}** (2% off).",
            'stage_two_offer': f"Good move! I will drop it to **{curr} {price_str}** (5% off). One final move left.",
            'final_offer': f"I'm going to my final floor! The lowest is **{curr} {price_str}**. Ready to lock it in? 🤝"
        }
        return eng_responses.get(stage_key, "An internal error occurred.")

    # Fixed floors
    VENDOR_MIN_ENGAGEMENT = product_price * Decimal('0.70')
    FINAL_FLOOR = round_price(product_price * Decimal('0.90'), product_price)
    STAGE_TWO_PRICE = round_price(product_price * Decimal('0.95'), product_price)
    STAGE_ONE_PRICE = round_price(product_price * Decimal('0.98'), product_price)
    
    last_ai_offer = product.negotiated_price or product_price
    
    if product.negotiated_price and product.negotiated_price <= FINAL_FLOOR and product.negotiated_price < product_price:
        return generate_response('already_agreed', round_price(product.negotiated_price, product_price))

    offer = None
    raw_offer_text = None 
    offer_match = re.search(r'([\d,\.]+\s*[km]?|\d+)', user_message, re.IGNORECASE)
    
    if offer_match:
        try:
            val = offer_match.group(1).lower().replace(',', '')
            if 'm' in val: offer = Decimal(val.replace('m', '')) * 1000000
            elif 'k' in val: offer = Decimal(val.replace('k', '')) * 1000
            else:
                val = re.sub(r'[^\d]', '', val)
                offer = Decimal(val).quantize(Decimal('0'))
            
            if offer < Decimal('10000') and product_price >= Decimal('100000'):
                 if offer * Decimal('1000') >= product_price * Decimal('0.5'):
                     offer *= Decimal('1000')
            raw_offer_text = f"{curr} {offer:,.0f}" 
        except: offer = None

    if offer is None:
        user_msg_lower = user_message.lower()
        if any(phrase in user_msg_lower for phrase in ['reduce', 'lower', 'final price', 'best price', 'discount', 'kundagaano', 'kankendeze', 'mpola', 'wansi']):
            if last_ai_offer >= product_price * Decimal('0.99'):
                new_price = STAGE_ONE_PRICE
            elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'):
                 new_price = STAGE_TWO_PRICE 
            elif last_ai_offer > FINAL_FLOOR + Decimal('1'):
                 new_price = FINAL_FLOOR
            else:
                 return generate_response('final_floor_rejection', FINAL_FLOOR, raw_offer_text)
            
            product.negotiated_price = new_price
            product.save()
            return generate_response('initial_ask_counter' if new_price==STAGE_ONE_PRICE else ('mid_ask_counter' if new_price==STAGE_TWO_PRICE else 'final_ask_counter'), new_price)
        return generate_response('default_query')

    if offer < VENDOR_MIN_ENGAGEMENT: 
        if last_ai_offer >= product_price * Decimal('0.99'):
             product.negotiated_price = STAGE_ONE_PRICE
             product.save()
             return generate_response('too_low_initial_counter', STAGE_ONE_PRICE, raw_offer_text)
        return generate_response('final_floor_rejection', last_ai_offer, raw_offer_text)

    if offer > product_price:
        product.negotiated_price = product_price
        product.save()
        return generate_response('too_high_offer', product_price, raw_offer_text)

    if offer >= FINAL_FLOOR:
        final_p = round_price(offer if offer < product_price else product_price, product_price)
        product.negotiated_price = final_p
        product.save()
        return generate_response('accept', final_p)
    
    if last_ai_offer >= product_price * Decimal('0.99'):
        new_price = STAGE_ONE_PRICE
        product.negotiated_price = new_price
        product.save()
        return generate_response('stage_one_offer', new_price, raw_offer_text)
    elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'):
        new_price = STAGE_TWO_PRICE
        product.negotiated_price = new_price
        product.save()
        return generate_response('stage_two_offer', new_price, raw_offer_text)
    elif last_ai_offer > FINAL_FLOOR + Decimal('1'):
        product.negotiated_price = FINAL_FLOOR
        product.save()
        return generate_response('final_offer', FINAL_FLOOR)
    else: 
        return generate_response('final_floor_rejection', FINAL_FLOOR, raw_offer_text)

def get_ai_response(request, product, user_message, chat_history):
    return get_gemini_negotiation_response(request, product, user_message, chat_history)

@login_required
def ai_negotiation_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    curr = product.get_currency_code()
    if not product.is_negotiable:
        messages.error(request, f"Price negotiation is not available for {product.name}.")
        return redirect('eshop:product_detail', slug=slug)

    form = NegotiationForm(request.POST or None)
    chat_history = request.session.get(f'chat_history_{slug}', None)
    
    if chat_history is None:
        initial_greeting = f"Hello! I'm the AI Negotiator, and I'm ready to find you a great price. The original price for **{product.name}** is {curr} {product.price:,.0f}. What is your first offer? (I also speak Luganda!)"
        chat_history = [{'role': 'ai', 'text': initial_greeting}]

    if request.method == 'POST' and form.is_valid():
        user_message = form.cleaned_data['user_message']
        chat_history.append({'role': 'user', 'text': user_message})
        ai_response_text = get_ai_response(request, product, user_message, chat_history)
        chat_history.append({'role': 'ai', 'text': ai_response_text})
        request.session[f'chat_history_{slug}'] = chat_history
        return redirect('eshop:ai_negotiation', slug=slug) 
        
    is_negotiation_active = product.negotiated_price and product.negotiated_price <= product.price * Decimal('0.90')

    context = {
        'product': product, 'form': form, 'chat_history': chat_history,
        'is_negotiation_active': is_negotiation_active, 'final_price': product.negotiated_price
    }
    return render(request, 'eshop/ai_negotiation.html', context)

@login_required
def accept_negotiated_price(request, slug):
    product = get_object_or_404(Product, slug=slug)
    curr = product.get_currency_code()
    cart = get_user_cart(request)
    if product.negotiated_price and product.negotiated_price <= product.price:
        CartItem.objects.filter(cart=cart, product=product).delete() 
        request.session.pop(f'chat_history_{slug}', None)
        request.session.pop(f'negotiation_language_{slug}', None)
        messages.success(request, f"🎉 Negotiated price of {curr} {product.negotiated_price:,.0f} accepted!")
        return redirect('eshop:product_detail', slug=slug)
    messages.error(request, "Oops! You must successfully negotiate first.")
    return redirect('eshop:ai_negotiation', slug=slug)

@login_required
def export_products_json(request):
    products = Product.objects.all()
    data = serialize('json', products, fields=('name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'language_tag'))
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="products.json"'
    return response
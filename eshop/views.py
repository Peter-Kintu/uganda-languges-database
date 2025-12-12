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
from django.http import HttpResponse
import os # For getting the API Key (simulated)


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
    """
    Displays the list of products for sale.
    """
    products = Product.objects.all().order_by('-id')
    
    # Ensure cart context is available for base.html
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
    
    return render(request, 'eshop/product_list.html', {
        'products': products,
        'cart': cart,
        'cart_total': cart_total,
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
        cart_item.refresh_from_db() # Refresh to get the updated quantity
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

    # Assuming all items belong to a single vendor for simplicity in this stage
    first_item = cart.items.first()
    vendor_name = first_item.product.vendor_name
    vendor_phone = first_item.product.whatsapp_number
    cart_total = cart.cart_total
    total_items_count = cart.items.aggregate(total=Sum('quantity'))['total']

    # Build the message content for the vendor
    order_items = "\n".join([f"- {item.quantity} x {item.product.name} @ UGX {item.product.price}" for item in cart.items.all()])
    
    order_message = (
        f"Hello {vendor_name},\n\n"
        f"🎉 A new order has been confirmed!\n\n"
        f"🛍️ Items:\n{order_items}\n\n"
        f"💰 Total: UGX {cart_total:,.0f}\n"
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
    """
    Displays the form for capturing the delivery location.
    """
    return render(request, 'eshop/delivery_location.html')

@login_required
def process_delivery_location(request):
    """
    Processes the delivery location form submission, stores data in the session, 
    and redirects to the order confirmation page.
    """
    if request.method == 'POST':
        # Retrieve data from the form
        address = request.POST.get('address_line1', '').strip()
        city = request.POST.get('city', '').strip()
        phone = request.POST.get('phone', '').strip()
        latitude = request.POST.get('latitude', 'N/A')
        longitude = request.POST.get('longitude', 'N/A')
        
        # Basic validation (a proper Form class should be used for real validation)
        if not all([address, city, phone]):
             messages.error(request, "Please fill in all required delivery details (Address, City, Phone).")
             return redirect('eshop:delivery_location')

        # Store delivery details in the session 
        request.session['delivery_details'] = {
            'address': address,
            'city': city,
            'phone': phone,
            'latitude': latitude,
            'longitude': longitude,
        }
        
        messages.success(request, "Delivery location confirmed! Please proceed to order confirmation.")
        # Redirect to the next step in the checkout flow
        return redirect('eshop:confirm_order_whatsapp') 
        
    return redirect('eshop:delivery_location')


@login_required
def confirm_order_whatsapp(request):
    """
    Redirects the user to WhatsApp with the order details and clears the cart.
    Now includes delivery details from session.
    """
    cart = get_user_cart(request)
    # Get and clear session data
    delivery_details = request.session.pop('delivery_details', None) 
    
    if not cart.items.exists():
        messages.error(request, "Your cart is empty. Cannot confirm an empty order.")
        return redirect('eshop:product_list')
        
    if not delivery_details:
        messages.error(request, "Delivery details are missing. Please re-enter your location.")
        return redirect('eshop:delivery_location')

    # Get vendor details (assuming one vendor per cart)
    first_item = cart.items.first()
    vendor_name = first_item.product.vendor_name
    vendor_phone = first_item.product.whatsapp_number

    # Build poetic WhatsApp message
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
        # Defensive check in the loop for good measure
        if item.product:
            lines.append(f"- {item.quantity} x {item.product.name} @ UGX {item.product.price}")
        else:
             lines.append(f"- {item.quantity} x [UNAVAILABLE PRODUCT]")


    lines.append("")
    lines.append(f"💰 Total: UGX {cart.cart_total:,.0f}")
    lines.append("")
    lines.append("Please prepare for delivery. Uganda thanks you.")

    message = "\n".join(lines)
    whatsapp_url = f"https://wa.me/{vendor_phone}?text={quote(message)}"

    # Optional: clear cart after confirmation
    cart.items.all().delete()
    cart.is_active = False
    cart.save()
    return redirect(whatsapp_url)


# Helper function for price rounding for a more natural feel
def round_price(price, product_price_ref):
    # Round to 2 decimal places for safety, then apply rounding based on magnitude
    price = price.quantize(Decimal('0.00')) 
    if product_price_ref >= Decimal('100000'):
         # Round to the nearest thousand 
         return Decimal(round(price / Decimal('1000')) * Decimal('1000'))
    elif product_price_ref >= Decimal('1000'):
         # Round to the nearest hundred
         return Decimal(round(price / Decimal('100')) * Decimal('100'))
    else:
         return price.quantize(Decimal('0.00')) 


# NEW: Helper function to detect if the user's message is likely in Luganda
def is_luganda(text):
    """Simple heuristic to detect Luganda phrases related to negotiation."""
    text_lower = text.lower()
    luganda_keywords = [
        'nsaba', 'nzikiriza', 'ogulire', 'kikula', 'kitono', 'wansi',
        'ogatta', 'nsasule', 'mpola', 'sente', 'ogwa', 'tunda', 'muwendo',
        'kundagaano', 'kankendeze' # Added common phrases
    ]
    # Check if a few common Luganda words are present
    if sum(1 for keyword in luganda_keywords if keyword in text_lower) >= 2:
        return True
    return False

# NEW: Simulated Luganda Responses for the fixed negotiation stages
def get_luganda_response(stage, price_str, offer_text="omusaala gwo"):
    """Returns a Luganda equivalent for the negotiation stage."""
    # Ensure price_str is comma-formatted (like 100,000)
    
    if stage == 'accept':
        return f"Wewawo! **UGX {price_str}** tukoze endagaano. Twagasseeko ogubadde ogw'oluvannyuma. Kanda ku 'Lock In' wansi ofune eky'omuzingo kino. 🎉"
    elif stage == 'final_floor_rejection':
        return f"Mpulidde {offer_text}, naye nsonyiwa, **UGX {price_str}** ogwo gwe musaala ogw'oluvannyuma nzekka gwe nsobola okuwa. Fuba okutuukirira. 🤝"
    elif stage == 'initial_ask_counter': # 98%
        return f"Mpulidde ekirowoozo kyo. Okusooka, nina okuwa **UGX {price_str}** (ekya 2% kiggyiddwako). Kiki eky'oluvannyuma ky’olina okuwa?"
    elif stage == 'mid_ask_counter': # 95%
        return f"Kuba nti obadde osaba, nkukendeezezzaako ku **UGX {price_str}** (ekya 5% kiggyiddwako). Oli kumpi n'omusaala ogw'oluvannyuma. Wandiwadde omuwendo ogusinga guno?"
    elif stage == 'final_ask_counter': # 90%
        return f"Kino kye kiggya eky'oluvannyuma! Omuwendo ogusembayo gw'oyinza okufuna gwe **UGX {price_str}** (ekya 10% kiggyiddwako). Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    elif stage == 'too_low_initial_counter':
        return f"Nsonyiwa, {offer_text} guli wansi nnyo. Kyokka, nina okutandikira ku **UGX {price_str}** (2% off) okutandika endagaano. Fuba okukuwa omuwendo ogusinga."
    elif stage == 'default_query':
        return "Nkyasobola okutegeera kye wategeeza. Fuba okuwa omusaala ogw'enkyukakyuka (nga 'UGX 80,000') oba nsaba nkukendeezeeko omuwendo. Genda mu maaso."
    elif stage == 'already_agreed':
        return f"Tugenze! Twakkiriziganyizza ku **UGX {price_str}**. Kanda ku 'Lock In' wansi."
    elif stage == 'too_high_offer':
        return f"{offer_text} ogwo guli waggulu nnyo! Nnina okukuguliza ku **UGX {price_str}** ogw'oluvannyuma. Kanda ku 'Lock In' ofune eky'omuzingo. 😊"
    elif stage == 'stage_one_offer': # Counter to price offer, move to 98%
        return f"Mpulidde {offer_text}. Nga bwe tusalira, nina okuwa **UGX {price_str}** (2% off). Omusango gw’olina okuddamu?"
    elif stage == 'stage_two_offer': # Counter to price offer, move to 95%
        return f"Endagaano ennungi! Nkubuusa ku **UGX {price_str}** (5% off). Oli kumpi n'omusaala ogw'oluvannyuma. Omuwendo gwo oguddako gwa ssente mmeka?"
    elif stage == 'final_offer': # Counter to price offer, move to 90%
        return f"Nzigidde ebyo byonna byange! Omuwendo ogw'oluvannyuma gw'oyinza okufuna gwe **UGX {price_str}**. Gwe musaala ogw'oluvannyuma. Nzikiriza?"
    
    return "Error in translation simulation." # Should not happen


# ------------------------------------
# GEMINI API INTEGRATION POINT (Simulated)
# ------------------------------------

# In a live environment, you would import the Gemini client here:
# from google import genai 
# GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_API_KEY_HERE")
# client = genai.Client(api_key=GEMINI_API_KEY)

def get_gemini_negotiation_response(product, user_message, chat_history):
    """
    Simulates a negotiation response generated by a powerful LLM (Gemini).
    The logic is structured to strictly follow the user's rules: 
    Fixed drops at 2%, 5%, and 10% off the original price, and a 70% floor.
    FIXED: Stricter price parsing and defensive counter-offers.
    NEW: Now handles basic language detection for a simulated Luganda response.
    """
    product_price = product.price

    # 0. Detect Language Preference
    is_luganda_session = is_luganda(user_message)

    # --- Helper to generate the final response (in English or Luganda) ---
    def generate_response(stage_key, price=None, raw_offer_text=None):
        # Format the price for display
        price_str = f"{price:,.0f}" if price is not None else "N/A"
        
        if is_luganda_session:
            return get_luganda_response(stage_key, price_str, raw_offer_text)
        
        # English Responses
        if stage_key == 'accept':
            return f"Yes! **UGX {price_str}** is an agreement. We have a deal! I've locked in the final price for you. Please click the 'Lock In' button to grab it before someone else does! 🎉"
        elif stage_key == 'final_floor_rejection':
             return f"I appreciate the offer of **{raw_offer_text}**, but it's too low for us to even consider. My current price remains **UGX {price_str}**. You need to offer a number closer to that."
        elif stage_key == 'initial_ask_counter':
            return f"I hear you! Just for asking, I can start our negotiation at the 2% drop: **UGX {price_str}**. What is your counter-offer?"
        elif stage_key == 'mid_ask_counter':
             return f"Since you asked for the best price, I will drop it again to the 5% drop: **UGX {price_str}**. I have one final move after this. Can you offer a number closer to my final floor?"
        elif stage_key == 'final_ask_counter':
             return f"This is the last chance! The lowest price I can give you is the 10% final floor: **UGX {price_str}**. This is the final offer. What do you say?"
        elif stage_key == 'default_query':
            return "I'm not sure how to process that. To keep things moving, please make a clear price offer (e.g., 'UGX 80,000') or ask me to reduce the current price."
        elif stage_key == 'already_agreed':
            return f"We've already agreed on a sweet deal of **UGX {price_str}**! Go ahead and click the 'Lock In' button below to secure it. 🔒"
        elif stage_key == 'too_low_initial_counter':
            return f"I appreciate the offer of **{raw_offer_text}**, but it's far too low. I will, however, drop the price to **UGX {price_str}** (2% off) to start the negotiation. Please make me a better offer."
        elif stage_key == 'too_high_offer':
             return f"Your offer of {raw_offer_text} is actually higher than the original asking price! We'll happily sell it to you for the original **UGX {price_str}**. Click 'Lock In' to secure the deal. Thanks! 😊"
        elif stage_key == 'stage_one_offer':
            return f"I appreciate your offer of {raw_offer_text}. Since this is our first counter, I can drop it to **UGX {price_str}** (2% off). What is your next move to get to my final price?"
        elif stage_key == 'stage_two_offer':
            return f"That's a good move! I will drop the price to **UGX {price_str}** (5% off). This is the second stage. I have only one final move left. Will you make a better offer?"
        elif stage_key == 'final_offer':
             return f"I'm going all the way to my final floor for you! The lowest I can possibly go is **UGX {price_str}** (10% off). This is the absolute final price. Are you ready to lock it in? 🤝"
        
        return "An internal error occurred." # Fallback


    # Define fixed negotiation floors (based on user request: 2%, 5%, and 10% off)
    VENDOR_MIN_ENGAGEMENT = product_price * Decimal('0.70')  # Absolute rejection floor (70%)
    
    # Target Prices (The AI's fixed offers, rounded for a natural feel)
    FINAL_FLOOR = round_price(product_price * Decimal('0.90'), product_price) # 10% off
    STAGE_TWO_PRICE = round_price(product_price * Decimal('0.95'), product_price) # 5% off
    STAGE_ONE_PRICE = round_price(product_price * Decimal('0.98'), product_price) # 2% off
    
    last_ai_offer = product.negotiated_price or product_price
    
    # 1. Check for acceptance status (already finalized)
    if product.negotiated_price and product.negotiated_price <= FINAL_FLOOR and product.negotiated_price < product_price:
        display_price = round_price(product.negotiated_price, product_price)
        return generate_response('already_agreed', display_price)

    # 2. Parse user offer - Robust Parsing (FIXED for stricter heuristic)
    offer = None
    raw_offer_text = None 
    
    # Regex to capture number formats like 2000000, 2,000,000, 200, 2m, etc.
    offer_match = re.search(r'([\d,\.]+\s*[km]?|\d+)', user_message, re.IGNORECASE)
    
    if offer_match:
        try:
            raw_match_group = offer_match.group(1).strip()
            # Clean up the string by removing non-digit characters except for a single potential decimal point
            cleaned_str = raw_match_group.lower().replace(',', '')
            
            # Handle suffixes (k/m)
            if 'm' in cleaned_str:
                cleaned_str = cleaned_str.replace('m', '')
                offer = Decimal(cleaned_str) * Decimal('1000000')
            elif 'k' in cleaned_str:
                cleaned_str = cleaned_str.replace('k', '')
                offer = Decimal(cleaned_str) * Decimal('1000')
            else:
                 # Remove remaining non-digit characters (like '.') for pure integer UGX value
                cleaned_str = re.sub(r'[^\d]', '', cleaned_str)
                offer = Decimal(cleaned_str).quantize(Decimal('0'))
            
            # FIX: Stricter Heuristic for missing '000' (e.g., user types 200 meaning 200,000)
            # Only apply this aggressive heuristic if the number is small enough (< UGX 10,000)
            if offer < Decimal('10000') and product_price >= Decimal('100000'):
                 # Check if the "thousand" version is a credible offer (> 50% of original price)
                 if offer * Decimal('1000') >= product_price * Decimal('0.5'):
                     offer *= Decimal('1000')
            
            raw_offer_text = f"UGX {offer:,.0f}" 
            
        except (InvalidOperation, ValueError, AttributeError):
            offer = None
            raw_offer_text = None

    # 3. Negotiation Logic

    # 3a. User did NOT make a clear price offer (or parsing failed)
    if offer is None:
        user_msg_lower = user_message.lower()
        
        # Check for generic requests for discount/final price (includes Luganda keywords)
        if any(phrase in user_msg_lower for phrase in ['reduce', 'lower', 'final price', 'best price', 'last price', 'discount', 'kundagaano', 'kankendeze', 'mpola', 'wansi']):
            
            # Determine the next price stage to counter with
            if last_ai_offer >= product_price * Decimal('0.99'): # Start: Move to 98%
                new_price = STAGE_ONE_PRICE 
                product.negotiated_price = new_price
                product.save()
                return generate_response('initial_ask_counter', new_price)
            
            elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'): # At 98% range: Move to 95%
                 new_price = STAGE_TWO_PRICE 
                 product.negotiated_price = new_price
                 product.save()
                 return generate_response('mid_ask_counter', new_price)

            elif last_ai_offer > FINAL_FLOOR + Decimal('1'): # At 95% range: Move to 90% (Final)
                 new_price = FINAL_FLOOR
                 product.negotiated_price = new_price
                 product.save()
                 return generate_response('final_ask_counter', new_price)
            
            else: # Already at or below 90%
                display_price = FINAL_FLOOR
                return generate_response('final_floor_rejection', display_price, raw_offer_text)

        # Default fallback
        return generate_response('default_query')


    # --- User made a valid price offer (offer is NOT None) ---

    # 3b. Offer is TOO LOW (below 70% threshold) - FIXED to defend current price
    if offer < VENDOR_MIN_ENGAGEMENT: 
        
        # Determine the price AI is currently defending
        if last_ai_offer >= product_price * Decimal('0.99'):
             # If at original price, counter with the first stage
             display_floor = STAGE_ONE_PRICE
             product.negotiated_price = STAGE_ONE_PRICE
             product.save()
             return generate_response('too_low_initial_counter', display_floor, raw_offer_text)
        
        else:
             # If AI has already made a move, defend the last price it offered. (No reset)
             display_floor = last_ai_offer
             return generate_response('final_floor_rejection', display_floor, raw_offer_text)


    # 3c. Offer is higher than the original price
    if offer > product_price:
        final_price = product_price
        product.negotiated_price = final_price
        product.save()
        return generate_response('too_high_offer', final_price, raw_offer_text)


    # 3d. Offer MEETS OR EXCEEDS THE FINAL FLOOR (90%) - DEAL ACCEPTED
    if offer >= FINAL_FLOOR:
        final_price = offer if offer < product_price else product_price
        final_price = round_price(final_price, product_price)
        product.negotiated_price = final_price
        product.save()
        return generate_response('accept', final_price)
    
    
    # 3e. Staged Negotiation Logic (User's offer is lower than 90% but higher than 70%)
    
    # Current Price is at 100% or very close: Move to 98%
    if last_ai_offer >= product_price * Decimal('0.99'):
        new_price = STAGE_ONE_PRICE # 98%
        product.negotiated_price = new_price
        product.save()
        return generate_response('stage_one_offer', new_price, raw_offer_text)
        
    # Current Price is at 98% (or slightly below): Move to 95%
    elif last_ai_offer > STAGE_TWO_PRICE + Decimal('1'):
        new_price = STAGE_TWO_PRICE # 95%
        product.negotiated_price = new_price
        product.save()
        return generate_response('stage_two_offer', new_price, raw_offer_text)

    # Current Price is at 95% (or slightly below): Move to 90% (Final)
    elif last_ai_offer > FINAL_FLOOR + Decimal('1'):
        final_price = FINAL_FLOOR # 90%
        product.negotiated_price = final_price
        product.save()
        return generate_response('final_offer', final_price)
        
    # The price is already at the final floor (90%). Reiterate.
    else: 
        display_price = FINAL_FLOOR
        return generate_response('final_floor_rejection', display_price, raw_offer_text)


def get_ai_response(product, user_message, chat_history):
    # This is the entry point called by ai_negotiation_view
    return get_gemini_negotiation_response(product, user_message, chat_history)


@login_required
def ai_negotiation_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    # Check if negotiation is even allowed
    if not product.is_negotiable:
        messages.error(request, f"Price negotiation is not available for {product.name}.")
        return redirect('eshop:product_detail', slug=slug)

    form = NegotiationForm(request.POST or None)
    
    # Retrieve chat history from session
    chat_history = request.session.get(f'chat_history_{slug}', [
        # Updated initial greeting to be more human-like
        {'role': 'ai', 'text': f"Hello! I'm the AI Negotiator, and I'm ready to find you a great price. The original price for **{product.name}** is UGX {product.price:,.0f}. What is your first offer? (I also speak Luganda!)"}
    ])

    if request.method == 'POST' and form.is_valid():
        user_message = form.cleaned_data['user_message']
        
        # 1. Add user message to history
        chat_history.append({'role': 'user', 'text': user_message})

        # 2. Get AI response and add it to history
        # CALLS THE NEW/UPDATED LOGIC
        ai_response_text = get_ai_response(product, user_message, chat_history)
        chat_history.append({'role': 'ai', 'text': ai_response_text})
        
        # Save updated chat history to session
        request.session[f'chat_history_{slug}'] = chat_history
        # This prevents the form resubmission on refresh
        return redirect('eshop:ai_negotiation', slug=slug) 
        
    # Check for acceptance status for the template display
    # Check if negotiated_price is set and less than or equal to 90% of original price
    is_negotiation_active = product.negotiated_price and product.negotiated_price <= product.price * Decimal('0.90')

    context = {
        'product': product,
        'form': form,
        'chat_history': chat_history,
        # Pass status to template for button control and price display
        'is_negotiation_active': is_negotiation_active, 
        'final_price': product.negotiated_price
    }

    return render(request, 'eshop/ai_negotiation.html', context)

@login_required
def accept_negotiated_price(request, slug):
    product = get_object_or_404(Product, slug=slug)
    cart = get_user_cart(request)

    # Check if a negotiated price exists and is lower than the original price
    if product.negotiated_price and product.negotiated_price <= product.price:
        
        # Optionally remove the item from the cart if it was already there (to enforce adding with the new price)
        try:
            cart_item = CartItem.objects.get(cart=cart, product=product)
            cart_item.delete() 
        except CartItem.DoesNotExist:
            pass 
            
        # Clear chat history for this product
        if f'chat_history_{slug}' in request.session:
            del request.session[f'chat_history_{slug}']
            
        messages.success(request, f"🎉 Negotiated price of UGX {product.negotiated_price:,.0f} accepted! Add the product to your cart to proceed.")
        return redirect('eshop:product_detail', slug=slug)

    messages.error(request, "Oops! You must successfully negotiate a price with the bot first.")
    return redirect('eshop:ai_negotiation', slug=slug) # Redirect back to negotiation to continue


# ------------------------------------
# Admin/Utility Views
# ------------------------------------

@login_required
def export_products_json(request):
    """
    Exports all products as a JSON file.
    This view is intended for use in the Django admin interface.
    """
    products = Product.objects.all()
    # Note: 'serialize' must be imported from 'django.core.serializers' at the top of views.py
    data = serialize('json', products, fields=('name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'language_tag'))
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="products.json"'
    return response
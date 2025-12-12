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
         return Decimal(round(price, -3)) 
    elif product_price_ref >= Decimal('1000'):
         # Round to the nearest hundred
         return Decimal(round(price, -2)) 
    else:
         return price.quantize(Decimal('0.00')) 

def get_ai_response(product, user_message, chat_history):
    """
    Updated AI negotiation logic for a more iterative, staged human-like feel: 98% -> 95% -> 90%.
    """
    product_price = product.price

    # Define negotiation constants (as requested: 98%, 95%, 90%)
    VENDOR_MIN_ENGAGEMENT = Decimal('0.70')  # Absolute rejection floor (70%)
    ABSOLUTE_FLOOR = product_price * Decimal('0.90') # The firm final stand (90%)
    STAGE_TWO_FLOOR = product_price * Decimal('0.95') # Mid-negotiation floor (95%)
    STAGE_ONE_OFFER = product_price * Decimal('0.98') # Initial counter (98%)

    # The AI's move factor will be aggressive to quickly hit the first two stages, 
    # and then aggressive to hit the final stage.
    AGRESSIVE_FACTOR = Decimal('0.50') # Move 50% of the distance
    RELENT_FACTOR = Decimal('0.20')    # Move 20% of the distance

    # 1. Check for acceptance status (already finalized)
    if product.negotiated_price and product.negotiated_price < product_price:
        return f"We've already agreed on a sweet deal of **UGX {product.negotiated_price:,.0f}**! Go ahead and click the 'Lock In' button below to secure it. 🔒"


    # 2. Parse user offer
    offer_match = re.search(r'(\d{1,3}(?:,\d{3})*(?:\\.\d{1,2})?|\d+)', user_message, re.IGNORECASE)
    
    offer = None
    if offer_match:
        try:
            offer_str = offer_match.group(1).replace(',', '')
            offer = Decimal(offer_str).quantize(Decimal('0.00')) 
        except (InvalidOperation, ValueError):
            pass 


    # 3. Negotiation Logic
    last_ai_offer = product.negotiated_price or product_price


    # 3a. User did NOT make a clear price offer or is just asking for a discount
    if offer is None:
        user_msg_lower = user_message.lower()
        
        if any(phrase in user_msg_lower for phrase in ['reduce', 'lower', 'final price', 'best price', 'last price', 'discount']):
            
            # If the current price is the original price, immediately drop to the 98% stage
            if last_ai_offer >= product_price:
                new_price = round_price(STAGE_ONE_OFFER, product_price)
                product.negotiated_price = new_price
                product.save()
                return f"I hear you! Just for asking, I can start our negotiation at **UGX {new_price:,.0f}**. This is the first step toward a great deal. What is your counter-offer?"
            
            # If the current price is already at the 90% floor, reiterate
            if last_ai_offer <= ABSOLUTE_FLOOR + Decimal('1'): 
                display_price = round_price(ABSOLUTE_FLOOR, product_price)
                product.negotiated_price = display_price
                product.save()
                return f"My apologies, but **UGX {display_price:,.0f}** is the absolute lowest I can go. You must meet me here to make the purchase."
            
            # General request for a lower price (apply a token reduction to encourage a proper offer)
            # Use a slightly more aggressive factor to hit the staged prices quickly
            reduction = (last_ai_offer - ABSOLUTE_FLOOR) * AGRESSIVE_FACTOR
            new_price = last_ai_offer - reduction
            
            if new_price < ABSOLUTE_FLOOR:
                new_price = ABSOLUTE_FLOOR
                
            final_counter = round_price(new_price, product_price)
            product.negotiated_price = final_counter
            product.save()
            
            return f"I can always try to move a little closer. The price is now **UGX {final_counter:,.0f}**, but I need a clear counter-offer from you to move further."
        
        # Default fallback for unparsable text or initial greeting
        if len(chat_history) <= 2 and 'hello' in user_msg_lower:
            return f"Hello back! I'm ready to negotiate. Please tell me your first price offer for the **{product.name}** in UGX."

        return "I'm not sure how to process that. To keep things moving, please make a clear price offer (e.g., 'UGX 80,000') or ask me to reduce the current price."


    # --- User made a valid price offer (offer is NOT None) ---

    min_price_reject = product_price * VENDOR_MIN_ENGAGEMENT
    
    # 3b. Offer is TOO LOW (below 70% threshold)
    if offer < min_price_reject: 
        display_floor = product_price * Decimal('0.75') 
        return f"I appreciate the offer of **UGX {offer:,.0f}**, but it's too low for us to even consider. I can't let it go for less than **UGX {display_floor:,.0f}**. Please make me a better offer."

    # 3c. Offer is higher than the original price
    if offer > product_price:
        final_price = product_price
        product.negotiated_price = final_price
        product.save()
        return f"Your offer of UGX {offer:,.0f} is actually higher than the original asking price! We'll happily sell it to you for the original **UGX {final_price:,.0f}**. Click 'Lock In' to secure the deal. Thanks! 😊"


    # 3d. Offer MEETS OR EXCEEDS THE ABSOLUTE FLOOR (90%) - DEAL ACCEPTED
    if offer >= ABSOLUTE_FLOOR:
        final_price = offer if offer < product_price else product_price
        product.negotiated_price = final_price
        product.save()
        # This will accept the deal at 90% or the user's offer if higher than 90% but less than 100%
        return f"Yes! **UGX {final_price:,.0f}** is an agreement. We have a deal! I've locked in the final price for you. Please click the 'Lock In' button to grab it before someone else does! 🎉"
    
    # 3e. Staged Negotiation Logic (98% -> 95% -> 90%)
    
    # Stage 1: Initial move to 98%
    if last_ai_offer >= product_price * Decimal('0.985'): # Current price is near or at 100%
        if offer >= STAGE_ONE_OFFER:
            new_price = round_price(offer, product_price) # Accept user's offer if it's 98% or better
            if new_price < STAGE_ONE_OFFER:
                 new_price = round_price(STAGE_ONE_OFFER, product_price)

            product.negotiated_price = new_price
            product.save()
            return f"That's a strong offer! I can meet you at **UGX {new_price:,.0f}**. I can still come down further, but I need you to commit to another move!"
        else:
             # Counter at 98% (STAGE_ONE_OFFER) to start the process
            new_price = round_price(STAGE_ONE_OFFER, product_price)
            product.negotiated_price = new_price
            product.save()
            return f"I appreciate your offer of UGX {offer:,.0f}. I can drop to **UGX {new_price:,.0f}** to start. What is your next move?"


    # Stage 2: Moving from 98% toward 95%
    elif last_ai_offer >= product_price * Decimal('0.955'): # Current price is between 98.5% and 95.5%
        if offer >= STAGE_TWO_FLOOR:
            # User offered 95% or better, aggressively move to 95% to close this stage.
            new_price = round_price(STAGE_TWO_FLOOR, product_price)
            product.negotiated_price = new_price
            product.save()
            return f"Okay, you're close! I'm now at **UGX {new_price:,.0f}**. This is a great price, but I have one more final price I can offer if you push me! What is your next offer?"
        else:
            # User offered less than 95%, use the slow 20% factor toward the user's price (but don't go below 95%)
            reduction_amount = (last_ai_offer - offer) * RELENT_FACTOR
            counter_price = last_ai_offer - reduction_amount
            
            if counter_price < STAGE_TWO_FLOOR:
                counter_price = STAGE_TWO_FLOOR
            
            final_counter = round_price(counter_price, product_price)
            product.negotiated_price = final_counter
            product.save()
            return f"I see your offer of UGX {offer:,.0f}. I can only reduce the price to **UGX {final_counter:,.0f}** for now. Can you meet me a little closer to UGX {round_price(STAGE_TWO_FLOOR, product_price):,.0f}?"


    # Stage 3: Final push to 90% (Current price is near 95%)
    else: # Current price is near 95%
        # The AI is now in the final negotiation stage, aggressively moving to the 90% floor.
        
        # Check if the user is already at the floor or better
        if offer >= ABSOLUTE_FLOOR:
            final_price = round_price(offer, product_price)
            product.negotiated_price = final_price
            product.save()
            return f"Yes! **UGX {final_price:,.0f}** is the final price! I've locked it in. Please click the 'Lock In' button to purchase. Congratulations on a great deal! 🎉"
            
        
        # User is below the floor, or below the last counter-offer. Aggressively counter at 90%.
        display_price = round_price(ABSOLUTE_FLOOR, product_price)
        product.negotiated_price = display_price
        product.save()
        return f"I've checked with the vendor and this is their final, non-negotiable price! The lowest I can possibly go is **UGX {display_price:,.0f}**. This is the best deal available. Are you ready to lock it in? 🤝"
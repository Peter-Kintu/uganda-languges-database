from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.serializers import serialize
# FIX: Correctly import F and Sum for aggregation
from django.db.models import F, Sum 
from decimal import Decimal, InvalidOperation # Import InvalidOperation for robust number handling
from django.contrib.auth.decorators import login_required
# REMOVED: from languages import models # Line removed due to incorrect/redundant import

from .forms import ProductForm, NegotiationForm 
from .models import Product, Cart, CartItem
from django.utils import timezone
from datetime import timedelta
import re # Used for simple price extraction in AI negotiation
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
    # FIX: Use imported Sum from django.db.models
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


def get_ai_response(product, user_message, chat_history):
    """
    Updated AI negotiation logic for a more iterative, human-like feel.
    FIXED: Robust price parsing and accurate comparison to the 90% floor.
    """
    product_price = product.price

    # Define negotiation constants
    VENDOR_MIN_ACCEPT = Decimal('0.70')      # Absolute lowest offer AI will engage with (70%)
    VENDOR_NEGOTIATION_FLOOR = product_price * Decimal('0.90') # AI's firm final stand (90%)
    
    # Dynamic step factor: 30% to 50% of the distance
    STEP_FACTOR = Decimal(str(0.30 + len(chat_history) * 0.02)) 
    STEP_FACTOR = min(STEP_FACTOR, Decimal('0.50')) # Cap at 50%

    # Helper function for rounding
    def round_price(price, product_price_ref):
        # Round to 2 decimal places for safety, then apply rounding based on magnitude
        price = price.quantize(Decimal('0.00')) 
        if product_price_ref >= Decimal('100000'):
             return Decimal(round(price, -3)) # Round to the nearest thousand 
        elif product_price_ref >= Decimal('1000'):
             return Decimal(round(price, -2)) # Round to the nearest hundred
        else:
             return price.quantize(Decimal('0.00')) 
    
    # 1. Parse user offer - look for UGX followed by a number, or just a number
    # Improved regex to capture numbers accurately, including large ones.
    offer_match = re.search(r'UGX\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+)', user_message, re.IGNORECASE)
    
    offer = None
    if offer_match:
        try:
            # Clean up and convert the offer to Decimal
            offer_str = offer_match.group(1).replace(',', '')
            # Use quantize to ensure a fixed decimal point for comparison (e.g., '225000.00')
            offer = Decimal(offer_str).quantize(Decimal('0.00')) 
        except (InvalidOperation, ValueError):
            pass # Keep offer as None if conversion fails
    
    # Check for acceptance status (already finalized)
    if product.negotiated_price and product.negotiated_price < product_price:
        return f"We've already agreed on the amazing price of **UGX {product.negotiated_price:,.0f}**! Click the 'Lock In' button to proceed now. 🥳"

    
    # Get the AI's last offer, or start with the original price
    last_ai_offer = product.negotiated_price if product.negotiated_price and product.negotiated_price > product_price * Decimal('0.70') else product_price
    
    # Ensure the last_ai_offer is also properly rounded for consistent comparison with the floor
    # We round the floor price once for consistency.
    floor_price = round_price(VENDOR_NEGOTIATION_FLOOR, product_price)
    min_price_accept = round_price(product_price * VENDOR_MIN_ACCEPT, product_price)


    # 2. Negotiation Logic
    
    # 2a. User made a valid price offer
    if offer is not None:
        
        # 2a.1. Offer is TOO LOW (below 70% threshold)
        if offer < min_price_accept: 
            return f"Honestly, that price of **UGX {offer:,.0f}** is too low for us to even consider. I can't let it go for less than **UGX {min_price_accept:,.0f}**. What's your next move?"

        # 2a.2. Offer MEETS OR EXCEEDS THE FINAL FLOOR (90%) - DEAL ACCEPTED
        # Crucial fix: Compare the user's *parsed* and *quantized* offer directly to the *calculated* floor.
        if offer >= floor_price:
            final_price = offer if offer < product_price else product_price
            product.negotiated_price = final_price
            product.save()
            # New, human-like acceptance response
            return f"That's a fantastic price, **UGX {final_price:,.0f}**! We have a deal. I've set the final price, so click the 'Lock In' button to grab it before someone else does! 🎉"
        
        # 2a.3. Offer is between 70% and 90% (Iterative Counter)
        if offer < floor_price:
            
            # If the user's offer is already at or above the AI's last counter, accept it.
            if offer >= last_ai_offer:
                final_price = offer
                product.negotiated_price = final_price
                product.save()
                return f"Yes, I can accept that! **UGX {final_price:,.0f}** is a final price. Please click 'Lock In' now. 🥳"

            # Calculate the new counter-offer: move 30-50% of the distance toward the floor (90%)
            reduction_amount = (last_ai_offer - offer) * STEP_FACTOR 
            counter_price = last_ai_offer - reduction_amount
            
            # Ensure we don't counter-offer below the final floor
            if counter_price < floor_price:
                 counter_price = floor_price

            final_counter = round_price(counter_price, product_price)

            # Enforce the 90% floor after rounding
            if final_counter < floor_price:
                 final_counter = floor_price
                 
            # Store the new counter price
            product.negotiated_price = final_counter
            product.save()
            
            if final_counter <= floor_price + Decimal('0.01'):
                 # Final offer hit the floor price (90%)
                 return f"I've checked with the vendor, and they won't budge anymore. The **last price** I can offer you is **UGX {final_counter:,.0f}**. Is this a deal?"
            
            # Conversational counter-offer
            return f"I see your UGX {offer:,.0f} offer. I've managed to knock the price down to **UGX {final_counter:,.0f}** for you. Can you meet me there, or go a little higher?"
            

    # 2b. User did NOT make a price offer (e.g., "reduce for me", "hi", etc.)
    
    user_msg_lower = user_message.lower()
    
    if any(phrase in user_msg_lower for phrase in ['reduce', 'lower', 'final price', 'best price', 'last price', 'discount', 'can you do']):
        
        # If we are already at the floor, reiterate the floor price
        if last_ai_offer <= floor_price + Decimal('0.01'): 
            product.negotiated_price = floor_price # Ensure it's exactly the floor
            product.save()
            # Human-like response when stuck at the floor
            return f"My apologies, but **UGX {floor_price:,.0f}** is literally the lowest I can go. My hands are tied now. What's your final answer?"
        
        # If we are not at the floor, make a small, progressive move (e.g., 5% of the distance from current to floor)
        reduction = (last_ai_offer - floor_price) * Decimal('0.05') 
        new_price = last_ai_offer - reduction
        
        # Ensure we don't counter-offer below the final floor
        if new_price < floor_price:
            new_price = floor_price
            
        final_counter = round_price(new_price, product_price)
             
        if final_counter < floor_price: 
             final_counter = floor_price
             
        # Store the new price and respond
        product.negotiated_price = final_counter
        product.save()
        
        # Conversational move-down response
        return f"Since you asked nicely, I can shave a little more off. I can do **UGX {final_counter:,.0f}**. What is the best price you are willing to pay right now?"
        
    # Default fallback for unparsable text or initial greeting
    else:
        # Check if it's the first message and redirect to a clear instruction
        if len(chat_history) <= 2 and 'hello' in user_msg_lower:
            return f"Hello back! To start, just tell me your first price offer for the **{product.name}** in UGX."

        return "I'm not sure how to process that. Could you please make a clear price offer (e.g., 'UGX 80,000') or ask me to reduce the current price?"


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
        {'role': 'ai', 'text': f"Hello! I'm the AI Negotiator. The original price for **{product.name}** is UGX {product.price:,.0f}. What is your first offer?"}
    ])

    if request.method == 'POST' and form.is_valid():
        user_message = form.cleaned_data['user_message']
        
        # 1. Add user message to history
        chat_history.append({'role': 'user', 'text': user_message})

        # 2. Get AI response and add it to history
        ai_response_text = get_ai_response(product, user_message, chat_history)
        chat_history.append({'role': 'ai', 'text': ai_response_text})
        
        # Save updated chat history to session
        request.session[f'chat_history_{slug}'] = chat_history
        # This prevents the form resubmission on refresh
        return redirect('eshop:ai_negotiation', slug=slug) 
        
    # Check for acceptance status for the template display
    is_negotiation_active = product.negotiated_price and product.negotiated_price <= product.price * Decimal('0.90')

    context = {
        'product': product,
        'form': form,
        'chat_history': chat_history,
        # Pass status to template for button control and price display
        'is_negotiation_active': is_negotiation_active, 
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
            # Assuming price_at_purchase field exists on CartItem (or you'd need to create it for the negotiated price to persist)
            # cart_item.price_at_purchase = product.negotiated_price 
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
    data = serialize('json', products, fields=('name', 'description', 'price', 'is_negotiable', 'vendor_name', 'whatsapp_number', 'tiktok_url', 'language_tag'))
    response = HttpResponse(data, content_type='application/json')
    response['Content-Disposition'] = 'attachment; filename="products.json"'
    return response
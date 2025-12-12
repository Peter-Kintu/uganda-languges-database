from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.serializers import serialize
# FIX: Correctly import F and Sum for aggregation
from django.db.models import F, Sum 
from decimal import Decimal
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
            messages.error(request, "Oops! Please correct the errors below.")
    else:
        form = ProductForm()
        
    return render(request, 'eshop/add_product.html', {'form': form})

@login_required
def product_detail(request, slug):
    """
    Displays the details of a single product.
    """
    product = get_object_or_404(Product, slug=slug)
    
    # Ensure cart context is available for base.html
    cart = get_user_cart(request)
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
    
    return render(request, 'eshop/product_detail.html', {
        'product': product,
        'cart_total': cart_total,
    })

@login_required
def add_to_cart(request, product_id):
    """
    Adds a specified product to the user's cart.
    """
    product = get_object_or_404(Product, id=product_id)
    cart = get_user_cart(request)

    # Check for existing item
    try:
        cart_item = CartItem.objects.get(cart=cart, product=product)
        # If item already exists, increase quantity
        cart_item.quantity = F('quantity') + 1
        cart_item.save()
        cart_item.refresh_from_db() # Refresh to get the updated quantity
        messages.success(request, f"📦 Added another '{product.name}' to your cart. Total: {cart_item.quantity}")
    except CartItem.DoesNotExist:
        # If item does not exist, create new item
        CartItem.objects.create(
            cart=cart, 
            product=product, 
            quantity=1
        )
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
        messages.warning(request, f"🗑️ '{product_name}' was removed from your cart.")
    except CartItem.DoesNotExist:
        messages.error(request, "Item not found in your cart.")
        
    return redirect('eshop:view_cart')

@login_required
def checkout_view(request):
    """
    Initial step in the checkout process, summarizing the cart.
    """
    cart = get_user_cart(request)
    if not cart.items.exists():
        messages.warning(request, "Your cart is empty. Please add items to proceed to checkout.")
        return redirect('eshop:product_list')

    # Assuming all items in the cart are from one vendor for simplicity (first item's vendor)
    first_item = cart.items.first()
    vendor = first_item.product 
    
    total_items_count = cart.items.aggregate(count=Sum('quantity'))['count'] or 0
    cart_total = cart.cart_total

    # Prepare order message for WhatsApp
    order_message_parts = [
        "*NEW ORDER from Africana AI Market*",
        f"Items in Cart ({total_items_count}):",
    ]
    for item in cart.items.all():
        # Use negotiated_price if available, otherwise use original price for message
        price = item.product.negotiated_price if item.product.negotiated_price else item.product.price
        order_message_parts.append(f"- {item.product.name} x {item.quantity} @ UGX {price:,.0f} each")

    order_message_parts.append(f"\n*Estimated Total:* UGX {cart_total:,.0f}")
    order_message_parts.append("\n*Customer will provide delivery location after this step.*")
    order_message = "\n".join(order_message_parts)

    context = {
        'cart': cart,
        'cart_total': cart_total,
        'total_items_count': total_items_count,
        'vendor': vendor,
        'order_message': order_message,
    }
    return render(request, 'eshop/checkout.html', context)


@login_required
def delivery_location_view(request):
    """
    View to capture the user's delivery location and details.
    """
    # Check if cart is empty before allowing delivery location input
    cart = get_user_cart(request)
    if not cart.items.exists():
        messages.error(request, "Cannot set delivery location: Your cart is empty.")
        return redirect('eshop:product_list')

    # Optionally pre-populate from session if user navigates back
    delivery_details = request.session.get('delivery_details', {})
    
    return render(request, 'eshop/delivery_location.html', {
        'delivery_details': delivery_details
    })

# This is the view that *saves* the location and redirects to the correct WhatsApp number view
@login_required
def process_delivery_location(request):
    """
    Processes the delivery location form and stores details in the session.
    """
    if request.method != 'POST':
        return redirect('eshop:delivery_location')

    # Extract delivery details from POST data
    address = request.POST.get('address')
    city = request.POST.get('city')
    phone = request.POST.get('phone')
    latitude = request.POST.get('latitude')
    longitude = request.POST.get('longitude')

    if not all([address, city, phone, latitude, longitude]):
        messages.error(request, "Please fill in all required delivery details (Address, City, Phone) and confirm location on the map.")
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
    # Redirect to the next step in the checkout flow, which fetches the vendor number and redirects to WhatsApp
    return redirect('eshop:confirm_order_whatsapp') 

@login_required
def confirm_order_whatsapp(request):
    """
    Redirects the user to WhatsApp with the full order details, including delivery location.
    This view correctly uses the vendor's actual number.
    """
    cart = get_user_cart(request)
    delivery_details = request.session.get('delivery_details')

    if not cart.items.exists() or not delivery_details:
        messages.error(request, "Missing cart items or delivery details. Please re-check your order.")
        return redirect('eshop:view_cart')

    # 1. Get Vendor Phone Number (Assuming single vendor per cart for simplicity)
    first_item = cart.items.first()
    vendor_phone = first_item.product.whatsapp_number
    
    # 2. Prepare Order Message
    total_items_count = cart.items.aggregate(count=Sum('quantity'))['count'] or 0
    cart_total = cart.cart_total

    order_message_parts = [
        "*NEW DELIVERY ORDER from Africana AI Market*",
        f"Items in Cart ({total_items_count}):",
    ]
    for item in cart.items.all():
        price = item.product.negotiated_price if item.product.negotiated_price else item.product.price
        order_message_parts.append(f"- {item.product.name} x {item.quantity} @ UGX {price:,.0f} each")

    # Add Delivery Details
    order_message_parts.extend([
        f"\n*ESTIMATED TOTAL:* UGX {cart_total:,.0f}",
        "\n*Delivery Information (Please Confirm/Call Customer):*",
        f"Customer Phone: {delivery_details.get('phone')}",
        f"Address: {delivery_details.get('address')}, {delivery_details.get('city')}",
        f"GPS (Lat, Lng): {delivery_details.get('latitude')}, {delivery_details.get('longitude')}",
        f"Google Maps Link: https://www.google.com/maps/search/?api=1&query={delivery_details.get('latitude')},{delivery_details.get('longitude')}",
        "\nPlease reply to confirm the final price, delivery cost, and payment details. Thank you!"
    ])

    order_message = "\n".join(order_message_parts)
    
    # 3. Construct WhatsApp URL and Redirect
    whatsapp_url = f"https://wa.me/{vendor_phone}?text={quote(order_message)}"
    
    # After a successful redirect (or assumed successful redirect), clear the session data
    if 'delivery_details' in request.session:
        del request.session['delivery_details']
        
    # Mark cart as confirmed and deactivate it (or handle confirmation logic)
    cart.is_active = False
    cart.status = 'confirmed'
    cart.save()
    
    messages.success(request, f"Redirecting to vendor's WhatsApp chat ({vendor_phone}) to finalize the order.")
    return redirect(whatsapp_url)


# ------------------------------------
# AI Negotiation Views/Functions
# ------------------------------------

def get_ai_response(offer_text, product_slug, request):
    """
    Core AI logic for negotiation.
    """
    product = get_object_or_404(Product, slug=product_slug)
    product_price = product.price
    
    # Define price bounds (e.g., vendor accepts min 60% of original price)
    VENDOR_MIN_ACCEPT_RATIO = Decimal('0.65')
    floor_price = product_price * VENDOR_MIN_ACCEPT_RATIO
    
    # Get last AI offer from session (default to 100% of price if none exists)
    last_ai_offer = request.session.get(f'last_ai_offer_{product_slug}', product_price)
    
    # 1. Try to extract a numeric offer from the user's message
    offer_match = re.search(r'UGX\s*([\d,]+)', offer_text, re.IGNORECASE)
    
    if offer_match:
        try:
            offer_str = offer_match.group(1).replace(',', '')
            offer = Decimal(offer_str)
        except:
            return "I'm the AI Negotiator! Your offer must be a valid number. For example: 'My offer is UGX 80,000'."
        
        
        # 2. Check if the offer matches or exceeds the current negotiated price (if accepted)
        if product.negotiated_price and offer >= product.negotiated_price:
            return f"You've already agreed to UGX {product.negotiated_price:,.0f} and that is our final price! Click 'Accept Final Price' to proceed."

        # 3. Process the offer
        
        # 3a. Offer is too low
        min_price_accept = product_price * VENDOR_MIN_ACCEPT_RATIO # Minimum acceptable price for the vendor
        if offer < min_price_accept: 
            # Suggest a higher, more encouraging minimum
            display_floor = product_price * Decimal('0.85') 
            return f"That's a bit too low for my vendor, sorry! We need a better starting point to negotiate seriously. Try an offer closer to UGX {display_floor:,.0f} and we can talk!"

        # 3b. Offer is higher than or equal to the last AI offer
        elif offer >= last_ai_offer:
            request.session[f'last_ai_offer_{product_slug}'] = last_ai_offer
            return f"That's not a negotiation! My last offer was UGX {last_ai_offer:,.0f}. Try lowering your price, or make a counter-offer below that."

        # 3c. Offer is acceptable (between floor and last AI offer)
        else:
            # Calculate the new counter-offer. 
            # The AI moves halfway between the user's offer and its last offer, or to the floor, whichever is higher.
            # Max decrease from last offer is 50% of the difference between user's offer and last offer.
            difference = last_ai_offer - offer
            # AI will decrease its price by half the difference between the user's offer and the AI's last offer.
            ai_reduction = difference / Decimal('2')
            
            # Ensure the counter price never goes below the floor
            counter_price = max(last_ai_offer - ai_reduction, floor_price)
            final_counter = counter_price # Renamed for clarity

            # Update the last AI offer in the session
            request.session[f'last_ai_offer_{product_slug}'] = final_counter
            
            # Save the final agreed price to the product if it hits the floor
            if final_counter == floor_price:
                product.negotiated_price = floor_price
                product.save()
                return f"Fantastic! We've reached our absolute final position! My vendor accepts UGX {floor_price:,.0f} and can go no lower. Click 'Accept Final Price' to proceed now."
            
            # Human-like response generation
            if final_counter <= floor_price + Decimal('1000') and final_counter < last_ai_offer:
                # If AI is very close to the floor, express effort/finality
                return f"Wow, you're a tough negotiator! I've talked to the vendor and they've agreed to **one final drop** for you: UGX {final_counter:,.0f}. That's the best they can do. Deal?"
            elif final_counter < last_ai_offer:
                # Standard polite counter
                return f"I hear your offer of UGX {offer:,.0f}. That's a good move! Let's meet halfway. My counter-offer is UGX {final_counter:,.0f}. What is your next offer?"
            else:
                # If the AI couldn't move or the user's offer was bad (e.g. reduction was too small, final_counter didn't move)
                return f"Thanks for the offer, but we can't accept it yet. I can only move a little bit at a time. My current offer remains at UGX {final_counter:,.0f}."
                
    else:
        # Initial instruction or missing currency
        return "I'm the AI Negotiator! Tell me your best offer in Ugandan Shillings (UGX) and I'll see what my vendor is willing to accept. For example: 'My offer is UGX 80,000'."


@login_required
def ai_negotiation_view(request, slug):
    """
    Handles the chat interface for AI price negotiation.
    """
    product = get_object_or_404(Product, slug=slug)
    
    # Initialize or retrieve chat history from session
    chat_history = request.session.get(f'chat_history_{slug}', [
        {'role': 'ai', 'text': f"I'm the AI Negotiator! Tell me your best offer in Ugandan Shillings (UGX) and I'll see what my vendor is willing to accept. For example: 'My offer is UGX {product.price * Decimal('0.85'):,.0f}'."}
    ])
    
    if request.method == 'POST':
        form = NegotiationForm(request.POST)
        
        if form.is_valid():
            # FIX: Use .get() defensively to prevent the KeyError, 
            # in case the 'message' field was set to required=False in forms.py
            user_message = form.cleaned_data.get('message') 
            
            if user_message:
                # Add user message to history
                chat_history.append({'role': 'user', 'text': user_message})
                
                # Get AI response
                ai_response = get_ai_response(user_message, slug, request)
                
                # Add AI response to history
                chat_history.append({'role': 'ai', 'text': ai_response})
                
                # Save updated history back to session
                request.session[f'chat_history_{slug}'] = chat_history
                request.session.modified = True
                
                # Redirect to GET to prevent form resubmission
                return redirect('eshop:ai_negotiation', slug=slug)
            else:
                # If the message is empty/missing, add a user-friendly error and let the form re-render
                messages.error(request, "Please enter a non-empty offer or message to negotiate.")

    else:
        form = NegotiationForm()

    context = {
        'product': product,
        'chat_history': chat_history,
        'form': form,
        'current_price': product.price,
    }
    return render(request, 'eshop/ai_negotiation.html', context)


@login_required
def accept_negotiated_price(request, slug):
    """
    Handles the acceptance of the final negotiated price.
    """
    product = get_object_or_404(Product, slug=slug)
    cart = get_user_cart(request)
    
    if product.negotiated_price:
        # The price is agreed upon and saved to the product model
        
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
    return redirect('eshop:product_detail', slug=slug)


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
    response['Content-Disposition'] = 'attachment; filename="products_export.json"'
    return response
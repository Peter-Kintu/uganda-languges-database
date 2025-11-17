from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.core.serializers import serialize
# FIX: Correctly import F and Sum for aggregation
from django.db.models import F, Sum 
from decimal import Decimal

# REMOVED: from languages import models # Line removed due to incorrect/redundant import

from .forms import ProductForm, NegotiationForm 
from .models import Product, Cart, CartItem
from django.utils import timezone
from datetime import timedelta
import re # Used for simple price extraction in AI negotiation


# ------------------------------------
# Helper Functions
# ------------------------------------


def google_verification(request):
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

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


def confirm_order_whatsapp(request):
    """
    Redirects the user to WhatsApp with the order details and clears the cart.
    """
    cart = get_user_cart(request)
    
    if not cart.items.exists():
        messages.error(request, "Your cart is empty. Cannot confirm an empty order.")
        return redirect('eshop:product_list')

    # Get vendor details (assuming one vendor per cart)
    first_item = cart.items.first()
    vendor_name = first_item.product.vendor_name
    vendor_phone = first_item.product.whatsapp_number

    # Build poetic WhatsApp message
    lines = [
        f"Hello {vendor_name},",
        "🎉 A new order has been confirmed!",
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
    lines.append("📞 Buyer contact: A proud customer awaits.")
    lines.append("")
    lines.append("Please prepare for delivery. Uganda thanks you.")

    message = "\n".join(lines)
    whatsapp_url = f"https://wa.me/{vendor_phone}?text={quote(message)}"

    # Optional: clear cart after confirmation
    cart.items.all().delete()
    cart.is_active = False
    cart.save()
    return redirect(whatsapp_url)

# ------------------------------------
# AI Price Negotiation Logic
# ------------------------------------

def get_ai_response(product, user_message, chat_history):
    """
    Simplified AI negotiation logic.
    """
    product_price = product.price

    # 1. Parse user offer
    offer_match = re.search(r'UGX\s*(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)', user_message, re.IGNORECASE)
    
    if offer_match:
        try:
            # Clean up and convert the offer to Decimal
            offer_str = offer_match.group(1).replace(',', '')
            offer = Decimal(offer_str)
        except:
            return "I'm the AI Negotiator! Your offer must be a valid number. For example: 'My offer is UGX 80000'."
    else:
        # Initial instruction or missing currency
        return "I'm the AI Negotiator! Tell me your best offer in Ugandan Shillings (UGX) and I'll see what my vendor is willing to accept. For example: 'My offer is UGX 80000'."
    
    # 2. Check for negotiation status (already finalized)
    if product.negotiated_price and product.negotiated_price < product.price:
        return f"We already agreed on a final price of UGX {product.negotiated_price:,.0f}! Click 'Accept Final Price' to proceed."

    # 3. Simple Negotiation Logic
    
    # 3a. Check for minimum acceptable price (60% of original price)
    # FIX: The check is now aligned with the minimum quoted to the user (60%)
    if offer < product_price * Decimal('0.6'): 
        return f"I appreciate your enthusiasm, but your offer is too low. My vendor's absolute minimum is UGX {product_price * Decimal('0.6'):,.0f}. Try again!"

    # 3b. Offer is near original price (accept it immediately)
    # Use Decimal('0.9') for consistent multiplication
    if offer >= product_price * Decimal('0.9'):
        final_price = offer
        # Store the negotiated price on the product instance
        product.negotiated_price = final_price
        product.save()
        return f"That is a very generous offer! UGX {final_price:,.0f} is a deal. I have marked this as the accepted price. Click 'Accept Final Price' to proceed."

    # 3c. Offer is in the negotiation range (60% to 90%)
    if offer < product_price:
        # Determine the counter-offer
        current_lowest = product_price * Decimal('0.7') # Vendor's true minimum selling price after negotiation
        
        # Simple counter: Meet them in the middle of their offer and the product price, but never below 70%
        # Use Decimal('2.0') for division
        counter_price = (offer + product_price) / Decimal('2.0') 
        if counter_price < current_lowest:
            counter_price = current_lowest

        # Round the counter price to a cleaner number
        final_counter = Decimal(round(counter_price, -3)) # Round to the nearest thousand

        # Set the product negotiated price to this new counter price
        product.negotiated_price = final_counter
        product.save()

        # Check if the counter is close to the user's offer
        if final_counter <= offer + Decimal('500'): # Use Decimal('500') for comparison
             product.negotiated_price = offer # Just give them what they offered
             product.save()
             return f"After consulting the elders, I accept your offer of UGX {offer:,.0f}! Click 'Accept Final Price' to proceed."
        else:
            return f"Hmm, I see your offer of UGX {offer:,.0f}. My vendor can only accept UGX {final_counter:,.0f}. What is your next move?"
    
    # 3d. Offer is higher than or equal to the original price
    if offer >= product_price:
        final_price = product_price
        product.negotiated_price = final_price
        product.save()
        return f"Your offer of UGX {offer:,.0f} is higher than the asking price! We will happily sell it to you for the original price of UGX {final_price:,.0f}. Click 'Accept Final Price' to proceed."
    
    # Fallback response
    return "I'm sorry, I seem to be having trouble understanding that. Please provide your offer in the format 'My offer is UGX 80000'."


def ai_negotiation_view(request, slug):
    product = get_object_or_404(Product, slug=slug)
    
    # Check if negotiation is even allowed
    if not product.is_negotiable:
        messages.error(request, f"Price negotiation is not available for {product.name}.")
        return redirect('eshop:product_detail', slug=slug)

    form = NegotiationForm(request.POST or None)
    
    # Retrieve chat history from session
    chat_history = request.session.get(f'chat_history_{slug}', [
        {'role': 'ai', 'text': f"I'm the AI Negotiator! Tell me your best offer in Ugandan Shillings (UGX) and I'll see what my vendor is willing to accept. The product price is UGX {product.price:,.0f}. For example: 'My offer is UGX 80000'."}
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
        
    context = {
        'product': product,
        'form': form,
        'chat_history': chat_history,
    }

    return render(request, 'eshop/ai_negotiation.html', context)


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
    return redirect('eshop:product_detail', slug=slug)


# ------------------------------------
# Admin/Utility Views
# ------------------------------------

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

# Placeholder for delivery_location_view (as it was implied in other files)
def delivery_location_view(request):
    """
    Placeholder for the delivery location view.
    """
    return render(request, 'eshop/delivery_location.html')
from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote
from django.contrib import messages
from django.http import HttpResponse
from django.core.serializers import serialize
from .forms import ProductForm
from .models import Product, Cart, CartItem
from django.utils import timezone
from datetime import timedelta


def product_list(request):
    """
    Displays the list of products for sale.
    """
    products = Product.objects.all().order_by('-id')
    return render(request, 'eshop/product_list.html', {
        'products': products
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
    return render(request, 'eshop/product_detail.html', {
        'product': product
    })
def ensure_session(request):
    if not request.session.session_key:
        request.session.save()


def add_to_cart(request, product_id):
    ensure_session(request)
    product = get_object_or_404(Product, id=product_id)
    session_key = request.session.session_key

    cart, created = Cart.objects.get_or_create(session_key=session_key)
    
    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={'quantity': 1}
    )
    
    if not item_created:
        cart_item.quantity += 1
        cart_item.save()

    messages.success(request, f"'{product.name}' was added to your cart.")
    return redirect('eshop:product_list')
    

# UPDATED: Use get_user_cart and ensure cart_total is in context
def view_cart(request):
    session_key = request.session.session_key
    cart = get_user_cart(request)
    
    # Calculate total safely to pass to template
    cart_total = cart.cart_total if cart and cart.items.exists() else 0
        
    if not cart or not cart.items.exists():
       messages.info(request, "🧺 Your basket is silent, waiting for treasures to speak.")

    return render(request, 'eshop/cart.html', {
        'cart': cart,
        'cart_total': cart_total,
    })
    
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id)
    if request.method == 'POST':
        item.delete()
    return redirect('eshop:view_cart')

# UPDATED: Use get_user_cart and ensure cart_total is in context
def checkout_view(request):
    """
    Displays the checkout page where users can review and confirm their order.
    """
    cart = get_user_cart(request) # Use the helper function to get an active cart
    
    # Calculate total safely to pass to template
    cart_total = cart.cart_total if cart and cart.items.exists() else 0

    if cart and cart.items.exists():
       language = cart.items.first().product.language_tag
       messages.info(request, f"Instructions available in {language} upon request.")

    return render(request, 'eshop/checkout.html', {
        'cart': cart,
        'cart_total': cart_total, # Pass total to template
    })

def get_user_cart(request):
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key

    # Expire old carts first
    Cart.objects.filter(
        session_key=session_key,
        updated_at__lt=timezone.now() - timedelta(days=2),
        status='open'
    ).update(status='expired')

    Cart.objects.filter(
    session_key=session_key,
    updated_at__lt=timezone.now() - timedelta(days=2),
    status='open',
    is_active=True
   ).update(status='expired', is_active=False)
    # Then get or create a fresh cart
    cart, _ = Cart.objects.get_or_create(session_key=session_key, is_active=True, status='open')
    return cart

def confirm_order_view(request):
    cart = get_user_cart(request)
    if not cart.items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect("eshop:product_list")

    # Assume one vendor per cart
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
        # NOTE: Using UGX for price unit as seen in the original code, assuming conversion is handled elsewhere or price is in UGX
        lines.append(f"- {item.quantity} x {item.product.name} @ UGX {item.product.price}")

    lines.append("")
    lines.append(f"💰 Total: UGX {cart.cart_total}")
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
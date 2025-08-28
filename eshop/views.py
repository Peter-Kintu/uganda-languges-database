from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.core.serializers import serialize
from .forms import ProductForm
from .models import Product, Cart, CartItem

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

def add_to_cart(request, product_id):
    """
    Handles adding a product to the shopping cart.
    """
    product = get_object_or_404(Product, id=product_id)
    if not request.session.session_key:
        request.session.save()
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

# Corrected view to fix the Server 500 error
def view_cart(request):
    session_key = request.session.session_key
    cart = None
    if session_key:
        try:
            cart = Cart.objects.get(session_key=session_key)
        except Cart.DoesNotExist:
            pass

    return render(request, 'eshop/cart.html', {
        'cart': cart
    })

def checkout_view(request):
    """
    Displays the checkout page where users can review and confirm their order.
    """
    session_key = request.session.session_key
    cart = None
    if session_key:
        try:
            cart = Cart.objects.get(session_key=session_key)
        except Cart.DoesNotExist:
            pass

    return render(request, 'eshop/checkout.html', {
        'cart': cart
    })

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
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import ProductForm
from .models import Product

# Unified view: submit + list products
def product_list(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f"🎉 '{product.name}' has been listed! Sell with pride.")
            return redirect('eshop:product_list')
        else:
            messages.error(request, "Oops! Something went wrong. Please check the form and try again.")
    else:
        form = ProductForm()

    products = Product.objects.all().order_by('-id')
    return render(request, 'eshop/product_list.html', {
        'form': form,
        'products': products
    })

# View for individual product details
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'eshop/product_detail.html', {'product': product})
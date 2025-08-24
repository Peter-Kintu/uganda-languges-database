from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import ProductForm
from .models import Product

# View for the seller submission form
def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('success_page')
    else:
        form = ProductForm()

    return render(request, 'eshop/create_product.html', {'form': form})

# View for listing all products
def product_list(request):
    products = Product.objects.all().order_by('-id')
    return render(request, 'eshop/product_list.html', {'products': products})

# View for the success page
def success_page(request):
    return render(request, 'eshop/success.html')

# View for individual product details
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    return render(request, 'eshop/product_detail.html', {'product': product})
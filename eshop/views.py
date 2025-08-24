from django.shortcuts import render, redirect
from .forms import ProductForm
from .models import Product

# View for the seller submission form
def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('success_page')  # Redirect to a success page or the product list
    else:
        form = ProductForm()
    
    return render(request, 'eshop/create_product.html', {'form': form})

# View for listing all products
def product_list(request):
    products = Product.objects.all().order_by('-id')  # Show most recent products first
    return render(request, 'eshop/product_list.html', {'products': products})

# You'll also need a detail view for individual products
def product_detail(request, slug):
    product = Product.objects.get(slug=slug)
    return render(request, 'eshop/product_detail.html', {'product': product})
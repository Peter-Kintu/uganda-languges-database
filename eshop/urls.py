from django.urls import path
from . import views

app_name = 'eshop'

urlpatterns = [
    # Core Product Views
    path('', views.product_list, name='product_list'),
    path('add/', views.add_product, name='add_product'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    
    # Cart Views
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    
    # Checkout & Confirmation Views
    path('checkout/', views.checkout_view, name='checkout'),
    path('delivery-location/', views.delivery_location_view, name='delivery_location'),
    path('confirm-order/', views.confirm_order_whatsapp, name='confirm_order_whatsapp'), 
    
    # Negotiation Feature URLs
    path('product/<slug:slug>/negotiate/', views.ai_negotiation_view, name='ai_negotiation'),
    path('product/<slug:slug>/accept-negotiated-price/', views.accept_negotiated_price, name='accept_negotiated_price'),
]
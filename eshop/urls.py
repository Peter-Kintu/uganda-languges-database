from django.urls import path
from . import views

app_name = 'eshop'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.add_product, name='add_product'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'), # NEW
    path('cart/', views.view_cart, name='view_cart'), # NEW
    path('checkout/', views.checkout_view, name='checkout'),
]
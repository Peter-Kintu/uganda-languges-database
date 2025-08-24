from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('sell/', views.create_product, name='create_product'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
]
from django.urls import path
from . import views

app_name = 'eshop'  #  Enables namespaced URL resolution

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('sell/', views.create_product, name='create_product'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('success/', views.success_page, name='success_page'),
]
from django.urls import path
from . import views

app_name = 'eshop'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('export-json/', views.export_products_json, name='export_products_json'),
]
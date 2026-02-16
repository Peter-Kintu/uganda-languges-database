from django.urls import path
from . import views

app_name = 'hotel'

urlpatterns = [
    # 1. Static/Specific paths first
    path('', views.hotel_list, name='hotel_list'),
    path('add/', views.add_accommodation, name='add_accommodation'),
    path('sync/', views.sync_hotels_travelpayouts, name='sync_hotels'), # FIXED ORDER
    
    # 2. Dynamic/Variable paths last
    path('hotel/<slug:slug>/', views.hotel_detail, name='hotel_detail'),
    path('book/<int:pk>/', views.book_hotel, name='book_hotel'),
]
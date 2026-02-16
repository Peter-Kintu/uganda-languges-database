from django.urls import path
from . import views

app_name = 'hotel'

# hotel/urls.py
urlpatterns = [
    path('', views.hotel_list, name='hotel_list'),
    path('add/', views.add_accommodation, name='add_accommodation'), # Add this line
    path('hotel/<slug:slug>/', views.hotel_detail, name='hotel_detail'),
    path('book/<int:pk>/', views.book_hotel, name='book_hotel'),
    path('sync/', views.sync_hotels_travelpayouts, name='sync_hotels'),
]

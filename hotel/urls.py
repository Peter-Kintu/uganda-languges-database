from django.urls import path
from . import views

app_name = 'hotel'

urlpatterns = [
    # 1. Main Directory Listing
    path('', views.hotel_list, name='hotel_list'),
    
    # 2. Management Actions (Must stay above slugs)
    path('add/', views.add_accommodation, name='add_accommodation'),
    path('sync/', views.sync_hotels_travelpayouts, name='sync_hotels'),
    
    # 3. Dynamic Details (Slugs are greedy, keep them at the bottom)
    path('hotel/<slug:slug>/', views.hotel_detail, name='hotel_detail'),
    
    # 4. Functional Redirects
    path('book/<int:pk>/', views.book_hotel, name='book_hotel'),
]
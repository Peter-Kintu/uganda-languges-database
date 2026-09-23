from django.urls import path

from . import views

app_name = 'logistics'

urlpatterns = [
    path('', views.ride_home, name='ride_home'),
    path('rides/request/', views.request_ride, name='request_ride'),
    path('rides/history/', views.ride_history, name='ride_history'),
    path('rides/<int:ride_id>/', views.ride_status, name='ride_status'),
    path('rides/<int:ride_id>/tracking/', views.ride_tracking, name='ride_tracking'),
    path('rides/<int:ride_id>/rate/', views.rate_ride, name='rate_ride'),
    path('rides/<int:ride_id>/safety/', views.safety_report, name='safety_report'),
    path('drivers/register/', views.register_driver, name='register_driver'),
    path('drivers/location/', views.driver_location, name='driver_location'),
    path('support/tickets/', views.create_support_ticket, name='create_support_ticket'),
    path('payments/<slug:provider_code>/webhook/', views.mobile_money_webhook, name='mobile_money_webhook'),
    path('orders/<int:order_id>/quote/', views.create_quote, name='create_quote'),
    path('orders/<int:order_id>/dispatch/', views.dispatch_order, name='dispatch_order'),
    path('shipments/<str:external_id>/', views.track_shipment, name='track_shipment'),
    path('webhooks/<slug:provider_code>/', views.provider_webhook, name='provider_webhook'),
]

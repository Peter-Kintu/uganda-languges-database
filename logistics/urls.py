from django.urls import path

from . import views

app_name = 'logistics'

urlpatterns = [
    path('orders/<int:order_id>/quote/', views.create_quote, name='create_quote'),
    path('orders/<int:order_id>/dispatch/', views.dispatch_order, name='dispatch_order'),
    path('shipments/<str:external_id>/', views.track_shipment, name='track_shipment'),
    path('webhooks/<slug:provider_code>/', views.provider_webhook, name='provider_webhook'),
]

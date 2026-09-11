from django.urls import path
from . import views
from .views import google_verification
from .views import robots_txt


app_name = 'eshop'

urlpatterns = [
    # Core Product Views
    path('googlec0826a61eabee54e.html', google_verification),
    path("robots.txt", robots_txt),
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
    path('process-delivery/', views.process_delivery_location, name='process_delivery'), 
    path('payment/', views.payment_view, name='payment'),
    path('payment/callback/', views.payment_callback, name='payment_callback'),
    path('confirm-order/', views.confirm_order_whatsapp, name='confirm_order_whatsapp'), 
    
    # Negotiation Feature URLs
    path('product/<slug:slug>/negotiate/', views.ai_negotiation_view, name='ai_negotiation'),
    path('product/<slug:slug>/negotiate/reset/', views.reset_negotiation, name='reset_negotiation'),
    path('product/<slug:slug>/accept-price/', views.accept_negotiated_price, name='accept_negotiated_price'),
    path('sync-aliexpress/', views.sync_aliexpress_products, name='sync_aliexpress'),
    path('buy/<int:product_id>/', views.buy_now, name='buy_now'),
    path('api/commerce-agent/', views.commerce_agent, name='commerce_agent'),
    path('api/merchant/inventory/', views.merchant_inventory, name='merchant_inventory'),
    path('api/merchant/inventory/sync/', views.merchant_inventory_sync, name='merchant_inventory_sync'),
    path('merchant/dashboard/', views.merchant_dashboard, name='merchant_dashboard'),
    path('api/merchant/verification/', views.submit_verification, name='submit_verification'),
    path('api/merchant/promotions/', views.create_promotion, name='create_promotion'),
    path('api/payments/start/', views.start_commerce_payment, name='start_commerce_payment'),
    path('api/payments/ipn/', views.commerce_payment_ipn, name='commerce_payment_ipn'),
    path('api/orders/<int:order_id>/confirm-delivery/', views.confirm_delivery, name='confirm_delivery'),
    path('orders/<int:order_id>/delivery-qr.png', views.delivery_qr, name='delivery_qr'),
    path('api/payouts/<int:payout_id>/disburse/', views.disburse_affiliate_payout, name='disburse_affiliate_payout'),
    path('api/voice-search/', views.voice_product_search, name='voice_product_search'),
    path('api/language-preference/', views.save_language_preference, name='save_language_preference'),
    path('api/whatsapp/catalog-sync/', views.whatsapp_catalog_sync, name='whatsapp_catalog_sync'),
    path('api/affiliate/click/', views.affiliate_click, name='affiliate_click'),
    path('api/live/sessions/', views.live_sessions, name='live_sessions'),
    # Temporary deletion route - remove after running
    # path('secret-delete-ali-products-9921/', views.temporary_delete_ali_products),
]
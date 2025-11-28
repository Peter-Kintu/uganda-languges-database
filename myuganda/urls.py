# myuganda/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from .sitemaps import JobPostSitemap, ProductSitemap, StaticViewSitemap  # Make sure you create this file

sitemaps_dict = {
    'static': StaticViewSitemap,
    'products': ProductSitemap, # NEW: Dynamic sitemap for Eshop products
    'jobs': JobPostSitemap,
}

urlpatterns = [
    # 1. INCLUDE USER APP URLs at the root level (path('', include('users.urls')))]
    path('', include('users.urls')), 
    
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('languages.urls')),
    path('eshop/', include('eshop.urls', namespace='eshop')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
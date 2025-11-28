# myuganda/urls.py

from django.contrib import admin
from django.urls import path, include, reverse_lazy # Import reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import RedirectView # Import RedirectView
from .sitemaps import JobPostSitemap, ProductSitemap, StaticViewSitemap 

sitemaps_dict = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'jobs': JobPostSitemap,
}

urlpatterns = [
    # 1. Root URLs for languages app (homepage) - Check this first for homepage
    path('', include('languages.urls')), 
    
    # 2. FIX: Map the conventional Django login URL (/accounts/login/) 
    # to redirect to the named URL defined in settings.py (users:user_login).
    # This correctly handles the redirect from @login_required decorator.
    path('accounts/login/', RedirectView.as_view(url=reverse_lazy('users:user_login')), name='accounts_login_redirect'),
    
    # 3. Include other user-related URLs (e.g., /login/, /register/, /profile/)
    path('', include('users.urls')), 
    
    path('admin/', admin.site.urls),
  
    path('eshop/', include('eshop.urls', namespace='eshop')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
    
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
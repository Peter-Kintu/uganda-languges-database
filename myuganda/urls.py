from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import RedirectView
from django.http import HttpResponse # Essential for returning the text key
from .sitemaps import JobPostSitemap, ProductSitemap, StaticViewSitemap 

sitemaps_dict = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'jobs': JobPostSitemap,
    
}

# Function to serve the IndexNow key directly from code
def index_now_key(request):
    key = "6102fc7f2225442b9772ed9b43d73ab1" # Updated key 
    return HttpResponse(key, content_type="text/plain")

urlpatterns = [
    # 1. Root URLs for languages app
    path('', include('languages.urls')), 

    # 2. Login Redirects
    path('accounts/login/', RedirectView.as_view(url=reverse_lazy('users:user_login')), name='accounts_login_redirect'),
    
    # 3. User URLs
    path('', include('users.urls')), 
    
    path('admin/', admin.site.urls),
    
    # IndexNow Key URL - Matches your file name 
    path('6102fc7f2225442b9772ed9b43d73ab1.txt', index_now_key),
    
    path('eshop/', include('eshop.urls', namespace='eshop')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic.base import RedirectView
from django.views.generic import TemplateView

from .sitemaps import JobPostSitemap, ProductSitemap, StaticViewSitemap 

sitemaps_dict = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'jobs': JobPostSitemap,
    
}



urlpatterns = [
    path("googled5b56ec94e5b9cb2.html",
         TemplateView.as_view(template_name="googled5b56ec94e5b9cb2.html")),

    # 1. Root URLs for languages app
    path('', include('languages.urls')), 

    # 2. Login Redirects
    path('accounts/login/', RedirectView.as_view(url=reverse_lazy('users:user_login')), name='accounts_login_redirect'),
    
    # 3. User URLs
    path('', include('users.urls')), 
    
    path('admin/', admin.site.urls),
    
    # IndexNow Key URL - Matches your file name 

    
    path('eshop/', include('eshop.urls', namespace='eshop')),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
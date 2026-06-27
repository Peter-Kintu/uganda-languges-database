from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from django.views.generic import TemplateView

from .sitemaps import JobPostSitemap, ProductSitemap, StaticViewSitemap, UserProfileSitemap, BusinessReelSitemap, custom_sitemap_view

import requests
from django.http import HttpResponse


def show_ip(request):
    ip = requests.get("https://api.ipify.org").text
    return HttpResponse(f"My public IP is: {ip}")


def ads_txt(request):
    content = "google.com, pub-9564790727166506, DIRECT, f08c47fec0942fa0\n"
    return HttpResponse(content, content_type="text/plain")

sitemaps_dict = {
    'static': StaticViewSitemap,
    'products': ProductSitemap,
    'movies': ProductSitemap,
    'jobs': JobPostSitemap,
    'profiles': UserProfileSitemap,
    'feeds': BusinessReelSitemap,
}

urlpatterns = [
    # Google verification file
    path("googled5b56ec94e5b9cb2.html",
         TemplateView.as_view(template_name="googled5b56ec94e5b9cb2.html")),

    # 1. Admin
    path("admin/", admin.site.urls),

    # 5. E‑shop
    path("eshop/", include("eshop.urls", namespace="eshop")),

    # 6. Hotels
    path("hotel/", include("hotel.urls", namespace="hotel")),

        # 2. Movies
    path("movie/", include("movie.urls", namespace="movie")), 


    path('social/', include('social.urls', namespace='social')), 


    # 2. Users (Authentication & Profile) at root
    path("", include("users.urls")),
    # Compatibility alias for legacy /users/... URLs
    path("users/", include("users.urls")),

    # 3. Languages App at root (jobs, recruiters, etc.)
    path(
        "languages/",
        RedirectView.as_view(pattern_name='languages:home', permanent=False),
        name='languages_redirect'
    ),
    path("", include("languages.urls")),

    # 4. Login Redirects (for third‑party apps expecting /accounts/login/)
    path("accounts/login/",
         RedirectView.as_view(url=reverse_lazy("users:user_login")),
         name="accounts_login_redirect"),

    

    # 7. SEO - Sitemap Index
    path("sitemap.xml", custom_sitemap_view, {"sitemaps": sitemaps_dict}, name="sitemap"),
    # Individual Sitemaps
    path("sitemap-<section>.xml", custom_sitemap_view, {"sitemaps": sitemaps_dict}, name="django.contrib.sitemaps.views.sitemap"),

    path("show-ip/", show_ip),
    path("ads.txt", ads_txt),
]

# Static & media serving in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

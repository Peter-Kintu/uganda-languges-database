from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.conf import settings
from django.http import HttpResponse
from django.contrib.sitemaps.views import sitemap as sitemap_view
from django.template.response import TemplateResponse
# FIX: Import all required models for dynamic sitemaps
from eshop.models import Product 
from languages.models import JobPost # Assuming JobPost is the model for the languages app

# 1. Sitemap for static, named URLs
class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            # FIX: Corrected URL names for the 'languages' app (Job Listings)
            'languages:home',
            'languages:post_job',          
            'languages:browse_job_listings', 
            'languages:recruiters_page',   
            'languages:featured_recruiter',

            # Eshop app static URLs
            'eshop:product_list',
            'eshop:add_product',
            'eshop:view_cart',
            'eshop:checkout',
            'eshop:delivery_location',
            'eshop:confirm_order_whatsapp',
            'users:user_login', # Adding the login URL is good practice
            'users:user_register', # Adding the register URL
        ]

    def location(self, item):
        return reverse(item)

# 2. Dynamic Sitemap for Product detail pages (Eshop app)
class ProductSitemap(Sitemap):
    priority = 0.6
    changefreq = 'daily'
    
    def items(self):
        # Returns all Product objects to generate URLs for each detail page
        try:
            return Product.objects.all()
        except Exception:
            return []

    def location(self, obj):
        try:
            # Uses the slug to reverse the URL 'eshop:product_detail'
            return reverse('eshop:product_detail', kwargs={'slug': obj.slug})
        except Exception:
            return '/eshop/products/'

# 3. Dynamic Sitemap for Job Post detail pages (Languages app)
class JobPostSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'
    
    def items(self):
        # Returns all validated JobPost objects
        try:
            return JobPost.objects.filter(is_validated=True).order_by('-timestamp')
        except Exception:
            return []

    def location(self, obj):
        try:
            # Uses the primary key (pk) to reverse the URL 'languages:job_post_detail'
            return reverse('languages:job_post_detail', kwargs={'pk': obj.pk})
        except Exception:
            return '/jobs/'

    def lastmod(self, obj):
        try:
            # Use the timestamp field to indicate the last modification date
            return obj.timestamp
        except Exception:
            return None


# 4. Custom Sitemap View - Replaces request domain with DEFAULT_DOMAIN setting
def custom_sitemap_view(request, sitemaps, section=None, template_name='sitemap.xml', content_type='application/xml'):
    """
    Custom sitemap view that replaces the request domain with the DEFAULT_DOMAIN setting.
    This ensures sitemaps always show www.africanaai.info instead of the Koyeb deployment URL.
    """
    # Get the standard sitemap response
    response = sitemap_view(request, sitemaps, section, template_name, content_type)

    # Ensure the sitemap response is rendered before reading content
    if hasattr(response, 'render') and not getattr(response, 'is_rendered', False):
        response = response.render()

    # Replace the Koyeb domain with the correct domain from settings
    if hasattr(response, 'content'):
        content = response.content.decode('utf-8')

        # Get the request domain (e.g., https://initial-danette-africana-60541726.koyeb.app)
        request_domain = f"https://{request.get_host()}"

        # Get the correct domain from settings (e.g., https://www.africanaai.info)
        correct_domain = f"https://{settings.DEFAULT_DOMAIN}"

        # Replace all occurrences of the request domain with the correct domain
        if request_domain != correct_domain:
            content = content.replace(request_domain, correct_domain)

        response.content = content.encode('utf-8')

    return response
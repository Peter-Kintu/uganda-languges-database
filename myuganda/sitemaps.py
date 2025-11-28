from django.contrib.sitemaps import Sitemap
from django.urls import reverse
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
        return Product.objects.all()

    def location(self, obj):
        # Uses the slug to reverse the URL 'eshop:product_detail'
        return reverse('eshop:product_detail', kwargs={'slug': obj.slug})

# 3. Dynamic Sitemap for Job Post detail pages (Languages app)
class JobPostSitemap(Sitemap):
    priority = 0.7
    changefreq = 'weekly'
    
    def items(self):
        # Returns all validated JobPost objects
        return JobPost.objects.filter(is_validated=True).order_by('-timestamp')

    def location(self, obj):
        # Uses the primary key (pk) to reverse the URL 'languages:job_post_detail'
        return reverse('languages:job_post_detail', kwargs={'pk': obj.pk})

    def lastmod(self, obj):
        # Use the timestamp field to indicate the last modification date
        return obj.timestamp
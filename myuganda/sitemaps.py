from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    priority = 0.8
    changefreq = 'weekly'

    def items(self):
        return [
            # Languages app (namespaced as 'languages')
            'languages:home',
            'languages:contribute',
            'languages:browse_contributions',
            'languages:sponsor',
            'languages:best_contributor',

            # Eshop app (namespaced as 'eshop')
            'eshop:product_list',
            'eshop:add_product',
            'eshop:view_cart',
            'eshop:checkout',
            'eshop:delivery_location',
            'eshop:confirm_order_whatsapp',
        ]

    def location(self, item):
        return reverse(item)
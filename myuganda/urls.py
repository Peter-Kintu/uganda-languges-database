"""
URL configuration for myuganda project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import: from my_app import views
    2. Add a URL to urlpatterns: path('', views.home, name='home')
Class-based views
    1. Add an import: from other_app.views import Home
    2. Add a URL to urlpatterns: path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns: path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
	# This URL pattern directs requests for the Django admin site to its default views.
	path('admin/', admin.site.urls),
	
	# This crucial line includes all URL patterns from the 'languages' app.
	# It ensures that all the paths defined in languages/urls.py are
	# correctly routed and can be found by name, resolving the 'NoReverseMatch' error.
	path('', include('languages.urls')),
	path('eshop/', include('eshop.urls')), # Corrected line
]

# This block is essential for serving static files (CSS, JS, images)
# when running the server with DEBUG = True. It's a common configuration
# for development environments.
if settings.DEBUG:
	urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    # This line includes the URLs from your new app.
    # Replace 'your_app_name' with the actual name of the app you created.
    path('', include('languages.urls')),
]
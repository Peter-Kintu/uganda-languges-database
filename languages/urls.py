from django.urls import path
from . import views

# A list of URL patterns for your 'languages' app.
urlpatterns = [
    # This new pattern routes the root URL to the 'browse_contributions' view.
    path('', views.browse_contributions, name='home'),
    
    # This pattern maps the '/contribute/' URL to the 'contribute' view.
    # It's named 'contribute' so we can reference it in templates.
    path('contribute/', views.contribute, name='contribute'),
    
    # This pattern maps the '/browse/' URL to the 'browse_contributions' view.
    # The name allows us to link to this page from other templates.
    path('browse/', views.browse_contributions, name='browse_contributions'),
    
    # This is the new URL pattern for the sponsorship page.
    # It maps '/sponsor/' to the 'sponsor' view and is named 'sponsor'.
    path('sponsor/', views.sponsor, name='sponsor'),
]

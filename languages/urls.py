# Django imports
from django.urls import path

# Import all view functions from your languages app
from . import views

# Set the app name for namespacing
app_name = 'languages'

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

    # This is the new URL pattern to handle 'liking' a contribution.
    # It expects an integer primary key (pk) in the URL to identify the contribution.
    # The `name` parameter is crucial for the {% url %} template tag to work correctly.
    path('like/<int:pk>/', views.like_contribution, name='like_contribution'),

    # This is the new URL pattern for exporting contributions to a JSON file.
    path('export_json/', views.export_contributions_json, name='export_json'),
]

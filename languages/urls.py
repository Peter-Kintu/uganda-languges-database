# Django imports
from django.urls import path

# Import all view functions from your languages app
from . import views

# Set the app name for namespacing. This is good practice
# and helps avoid URL name clashes between different apps.
app_name = 'languages'

urlpatterns = [
    # The root URL of the app, e.g., 'uganda-languges-database.onrender.com/'.
    # This maps to the 'browse_contributions' view and is named 'home'.
    path('', views.browse_contributions, name='home'),
    
    # URL for the main contribution page, e.g., '/contribute/'.
    # This maps to the 'contribute' view and is named 'contribute'.
    path('contribute/', views.contribute, name='contribute'),
    
    # URL for browsing all validated contributions, e.g., '/browse/'.
    # This maps to the same 'browse_contributions' view, but has a different name.
    # It's important to have this name for links that specifically go to '/browse/'.
    path('browse/', views.browse_contributions, name='browse_contributions'),
    
    # URL for the sponsorship page, e.g., '/sponsor/'.
    # This maps to the 'sponsor' view and is named 'sponsor'.
    path('sponsor/', views.sponsor, name='sponsor'),

    # This is the URL pattern to handle 'liking' a contribution, e.g., '/like/5/'.
    # It expects an integer primary key (pk) in the URL to identify the contribution.
    # The name 'like_contribution' is used by the form in your template.
    path('like/<int:pk>/', views.like_contribution, name='like_contribution'),

    # URL for exporting contributions to a JSON file, e.g., '/export_json/'.
    # This maps to the 'export_contributions_json' view and is named 'export_json'.
    path('export_json/', views.export_contributions_json, name='export_json'),
]

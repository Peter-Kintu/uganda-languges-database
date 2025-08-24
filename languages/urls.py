# Django imports
from django.urls import path

# Import all view functions from your languages app
from . import views

# Set the app name for namespacing. This is a best practice
# that helps prevent URL name clashes with other apps.
app_name = 'languages'

urlpatterns = [
    # The URL for the home page of the app. It's named 'home'.
    path('', views.browse_contributions, name='home'),
    
    # URL for the contribution page. This is where users can add new phrases.
    path('contribute/', views.contribute, name='contribute'),
    
    # This is the crucial URL pattern that you were trying to reverse.
    # It is explicitly named 'browse_contributions' and points to the
    # correct view. The error will disappear once this file is deployed
    # with the correct name.
    path('browse/', views.browse_contributions, name='browse_contributions'),
    
    # URL for the sponsorship page.
    path('sponsor/', views.sponsor, name='sponsor'),

    # This URL handles 'liking' a specific contribution.
    # It expects an integer primary key (pk) to identify the item.
    path('like/<int:pk>/', views.like_contribution, name='like_contribution'),

    # This URL handles exporting contributions to a JSON file.
    path('export_json/', views.export_contributions_json, name='export_json'),
]

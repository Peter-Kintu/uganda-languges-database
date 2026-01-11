# languages/urls.py

from django.urls import path
from . import views
from .views import google_verification, robots_txt, featured_recruiter_view

# Set the app name for namespacing.
app_name = 'languages'

urlpatterns = [
    # --- System & SEO ---
    path('googlec0826a61eabee54e.html', google_verification),
    path("robots.txt", robots_txt),

    # --- Core Job Platform ---
    # The root now acts as the primary Hybrid Job Feed
    path('', views.browse_job_listings, name='home'), 
    
    # Dedicated browse and search paths
    path('jobs/', views.browse_job_listings, name='browse_job_listings'),
    path('jobs/search/', views.browse_job_listings, name='job_search'), # Improved for SEO/Analytics
    
    # Specific Job Detail View
    path('job/<int:pk>/', views.job_post_detail, name='job_post_detail'),

    # --- Recruiter & Posting Actions ---
    path('post-job/', views.post_job, name='post_job'),
    path('recruiters/', views.recruiters_page, name='recruiters_page'),
    path('featured-recruiter/', featured_recruiter_view, name='featured_recruiter'),
    
    # --- User & Engagement ---
    path('profile/', views.user_profile, name='user_profile'),
    path('upvote/<int:pk>/', views.upvote_job_application, name='upvote_job_application'),
    
    # --- Auth & Data ---
    path('logout/', views.user_logout, name='user_logout'),    
    path('export/jobs-json/', views.export_contributions_json, name='export_contributions_json'),
    # path("careerjet/", careerjet_jobs),

]





















# # languages/urls.py

# from django.urls import path
# from . import views
# from .views import google_verification
# from .views import robots_txt
# from .views import featured_recruiter_view # Corrected Import: Replaced the non-existent view with the new, correct name.


# # Set the app name for namespacing. This is a best practice
# # that helps prevent URL name clashes with other apps.
# app_name = 'languages'

# urlpatterns = [
    
#     path('googlec0826a61eabee54e.html', google_verification),
#     path("robots.txt", robots_txt),
#     path('user_profile/', views.user_profile, name='user_profile'),
    
#     # The URL for the root of your application, pointing to the browse view.
#     path('', views.browse_job_listings, name='home'), # Updated view name
    
#     # URL for the job post page. (Was: 'contribute/')
#     path('post-job/', views.post_job, name='post_job'), # Updated path and name
#     path('job/<int:pk>/', views.job_post_detail, name='job_post_detail'),
   
    
#     # This URL is for browsing the job listings. (Was: 'browse/')
#     path('jobs/', views.browse_job_listings, name='browse_job_listings'), # Updated path and name
    
#     # URL for the recruiters page. (Was: 'sponsor/')
#     path('recruiters/', views.recruiters_page, name='recruiters_page'), # Updated path and name

#     # URL for the featured recruiter page (Best Contributor).
#     # This was the view causing the import error, now using the corrected view name.
#     path('featured/', featured_recruiter_view, name='featured_recruiter'),

    
#     # This URL handles 'upvoting' a specific job post. (Was: 'like/<int:pk>/')
#     path('upvote/<int:pk>/', views.upvote_job_application, name='upvote_job_application'), # Updated path and name

#     # This URL handles exporting contributions to a JSON file. (No name change for admin simplicity)
#     path('logout/', views.user_logout, name='user_logout'),    
#     path('export_contributions_json/', views.export_contributions_json, name='export_contributions_json'),
# ]

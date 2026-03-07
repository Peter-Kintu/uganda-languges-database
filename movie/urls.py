from django.urls import path
from . import views
from movie.views import sync_movies_view

# The app_name is critical for template tags like {% url 'movie:watch_now' ... %}
app_name = 'movie'

urlpatterns = [
    # 1. Main Catalog: Home page of the affiliate site
    path('', views.movie_list, name='movie_list'),

    path('admin/movie/sync-now/', sync_movies_view, name='sync_movies_admin'),
    
    # 2. Affiliate Redirection: Tracks clicks before sending to Amazon/Netflix
    # This uses <int:movie_id> to identify the movie in the database
    path('watch/<int:movie_id>/', views.watch_now, name='watch_now'), 
    
    # 3. Movie Detail: SEO-friendly URLs using slugs (e.g., /view/interstellar/)
    path('view/<slug:slug>/', views.movie_detail, name='movie_detail'),
]
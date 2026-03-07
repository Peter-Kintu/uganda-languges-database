from django.shortcuts import render, redirect, get_object_or_404
from .models import Movie, Order
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.admin.views.decorators import staff_member_required
from .sync_movies import fetch_trending_movies
from django.contrib import messages

@login_required
def movie_list(request):
    """
    The main catalog view. 
    Prioritizes 'AI Trending' movies to increase affiliate link visibility.
    """
    # Fetch all movies, newest first for the main grid
    movies = Movie.objects.all().order_by('-release_date')
    
    # AI Trending Logic: Pulls the most viewed movies for the top slider
    trending = Movie.objects.all().order_by('-view_count')[:5]
    
    # Handle search queries
    query = request.GET.get('search')
    if query:
        movies = movies.filter(
            Q(name__icontains=query) | Q(ai_recommendation_tags__icontains=query)
        )
        
    return render(request, 'movie/movie_list.html', {
        'movies': movies,
        'trending': trending
    })

@login_required
def movie_detail(request, slug):
    """
    Detailed view with AI-driven cross-selling.
    Shows similar movies to keep users clicking affiliate links.
    """
    movie = get_object_or_404(Movie, slug=slug)
    
    # AI Recommendation Logic: Match by genre or AI tags
    recommendations = Movie.objects.filter(
        Q(genre=movie.genre) | Q(ai_recommendation_tags__icontains=movie.genre)
    ).exclude(id=movie.id)[:4]

    # Increment view count for the Trending algorithm
    movie.view_count += 1
    movie.save()

    return render(request, 'movie/movie_detail.html', {
        'movie': movie,
        'recommendations': recommendations
    })

@login_required
def watch_now(request, movie_id):
    """
    The 'Money' view. 
    Redirects to the affiliate link and records a 'Redirected' order.
    """
    movie = get_object_or_404(Movie, id=movie_id)
    
    if movie.affiliate_url:
        # Record the click as an 'Order' with 'Redirected' status for tracking
        Order.objects.create(
            buyer=request.user,
            movie=movie,
            total_amount=movie.price or 0,
            status='Redirected'
        )
        
        # External redirect to your Amazon, Netflix, or Disney+ partner link
        return redirect(movie.affiliate_url)
        
    return redirect('movie:movie_list')

@staff_member_required
def sync_movies_view(request):
    try:
        fetch_and_store_movies()
        messages.success(request, "Movies synced successfully from TMDB!")
    except Exception as e:
        messages.error(request, f"Error syncing movies: {str(e)}")
    
    # Redirect back to the movie admin page
    return redirect('admin:movie_movie_changelist')    
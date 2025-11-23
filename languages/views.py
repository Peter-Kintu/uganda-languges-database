from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Count
from django.urls import reverse
from datetime import date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib.auth import  logout  # Make sure 'logout' is imported
from django.contrib import messages

# Updated Imports: PhraseContributionForm -> JobPostForm, 
# PhraseContribution, LANGUAGES, INTENTS -> JobPost, JOB_CATEGORIES, JOB_TYPES
from .forms import JobPostForm
from .models import JobPost, JOB_CATEGORIES, JOB_TYPES, Applicant 
# NEW IMPORT: Assume Product model is in the 'eshop' app
try:
    from eshop.models import Product 
except ImportError:
    # Fallback/Placeholder if eshop models are not in the path
    class Product:
        objects = None 


def google_verification(request):
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")


def robots_txt(request):
    lines = [
        "User-agent: *",
        "allow:",
        "Sitemap: https://initial-danette-africana-60541726.koyeb.app/sitemap.xml"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")     


# Renamed get_top_contributors to get_top_recruiters
@login_required
def get_top_recruiters(request, month=None, year=None, limit=10):
    """
    A helper function to find and count top recruiters (contributors).
    Returns a list of dicts: [{'recruiter_name': 'Name', 'post_count': X}].
    If month/year are provided, filters by that period.
    """
    
    # Start with all validated posts
    posts = JobPost.objects.filter(is_validated=True)
    
    # Filter by month and year if provided
    if month is not None and year is not None:
        posts = posts.filter(timestamp__month=month, timestamp__year=year)
        
    # Aggregate by recruiter_name and count the number of posts
    top_recruiters = posts.values('recruiter_name') \
        .annotate(post_count=Count('recruiter_name')) \
        .order_by('-post_count')[:limit]
        
    # Convert queryset to a list of dicts for consistent handling
    return list(top_recruiters)


# Helper to get top recruiters specifically for the current month
@login_required
def get_top_recruiters_of_the_month(request, limit=10):
    now = date.today()
    return get_top_recruiters(request, month=now.month, year=now.year, limit=limit)


# Renamed best_contributor_view to featured_recruiter_view (Resolves the ImportError by defining the correct name)
@login_required
def featured_recruiter_view(request):
    """
    Finds and displays the recruiter with the highest number of validated job posts 
    in the current month. If none are found, it falls back to the top recruiter 
    of all time. Renders 'best_contributor.html'.
    """
    featured_recruiter_data = None
    is_current_month = False

    # 1. Try to find the top recruiter for the current month
    current_month_recruiters = get_top_recruiters_of_the_month(request, limit=1)
    
    if current_month_recruiters:
        featured_recruiter_data = current_month_recruiters[0]
        is_current_month = True
    else:
        # 2. Fallback: Get the top recruiter of all time
        all_time_recruiters = get_top_recruiters(request, limit=1)
        featured_recruiter_data = all_time_recruiters[0] if all_time_recruiters else None
        is_current_month = False

    context = {}
    if featured_recruiter_data:
        context['recruiter_name'] = featured_recruiter_data['recruiter_name'] # Renamed context variable
        context['post_count'] = featured_recruiter_data['post_count'] # Renamed context variable
        context['is_current_month'] = is_current_month
    else:
        # Placeholder data if no contributions are found
        context['recruiter_name'] = "No Featured Recruiter Yet"
        context['post_count'] = 0
        context['is_current_month'] = True # Default to true for a blank slate

    return render(request, 'best_contributor.html', context)


# View to export all validated contributions as JSON
@login_required
def export_contributions_json(request):
    # Fetch only validated job posts
    validated_posts = JobPost.objects.filter(is_validated=True).values(
        'post_content', 
        'required_skills', 
        'job_category', 
        'job_type', 
        'recruiter_name', 
        'recruiter_location',
        'timestamp',
        'company_logo_or_media' # Including the new field
    )
    
    data = list(validated_posts)

    # Convert the queryset to a list for JSON serialization
    # Note: JobPost.timestamp is a datetime object, which JsonResponse handles fine.
    # FileField URLs (company_logo_or_media) are handled by the .values() method returning the URL string.
    
    response = JsonResponse(data, safe=False)
    # Set the content type and file name for the download
    response['Content-Disposition'] = 'attachment; filename="validated_job_posts.json"'
    return response


# View for handling new job post submissions (was: 'contribute')
@login_required
def post_job(request):
    if request.method == 'POST':
        # Need to include request.FILES because the form now handles a FileField
        form = JobPostForm(request.POST, request.FILES) 
        if form.is_valid():
            job_post = form.save(commit=False)
            
            # --- Auto-generate Applicant if needed ---
            
            recruiter_name = job_post.recruiter_name
            # Find an existing Applicant or create a new one.
            applicant, created = Applicant.objects.get_or_create(
                name=recruiter_name,
                # FIX APPLIED: Changed the key in defaults from 'recruiter_location' to 'location'
                defaults={'location': job_post.recruiter_location} 
            )
            job_post.applicant = applicant
            
            job_post.save()
            
            # Update the Applicant's total posts count
            # Use job_post.applicant to ensure we are operating on the correct/newly created applicant
            job_post.applicant.total_posts = job_post.applicant.jobpost_set.count()
            job_post.applicant.save()
            
            # After successful submission, redirect to the job listings page.
            return redirect(reverse('languages:browse_job_listings'))
    else:
        form = JobPostForm()
    
    # Renders the job post form page.
    return render(request, 'contribute.html', {'form': form})

# View for browsing and searching job listings (was: 'browse')
@login_required
def browse_job_listings(request):
    # Get filters from the request
    category_filter = request.GET.get('category')
    search_query = request.GET.get('q')
    
    # Start with all validated posts
    job_posts = JobPost.objects.filter(is_validated=True).order_by('-timestamp')
    
    # Apply category filter
    if category_filter and category_filter != 'all':
        job_posts = job_posts.filter(job_category=category_filter)
        
    # Apply search filter
    if search_query:
        # Search across post_content (job description), required_skills, and recruiter_name
        job_posts = job_posts.filter(
            Q(post_content__icontains=search_query) |
            Q(required_skills__icontains=search_query) |
            Q(recruiter_name__icontains=search_query)
        )

    # Pagination setup
    paginator = Paginator(job_posts, 10) # Show 10 posts per page
    page = request.GET.get('page')
    
    try:
        posts_on_page = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        posts_on_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g., 9999), deliver last page of results.
        posts_on_page = paginator.page(paginator.num_pages)

    context = {
        'job_posts': posts_on_page,
        'job_categories': JOB_CATEGORIES, # All categories for filter dropdown
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query or '',
        'page_title': "Job Listings"
    }
    
    return render(request, 'contributions_list.html', context)


# View for handling upvotes (was: 'like_phrase')
@require_POST
@login_required
def upvote_job_application(request, pk):
    """
    Handles the POST request to increment the upvote count for a specific job post.
    """
    # Get the job post object, or raise a 404 if it doesn't exist
    job_post = get_object_or_404(JobPost, pk=pk)
    
    # Atomically increment the 'upvotes' field
    job_post.upvotes = F('upvotes') + 1
    job_post.save(update_fields=['upvotes'])
    
    # Refresh the object to get the updated value
    job_post.refresh_from_db()
    
    # Return the new upvote count as a JSON response
    return JsonResponse({'success': True, 'new_upvotes': job_post.upvotes})


# View for the main recruiters/sponsorship page (was: 'sponsor')
@login_required
def recruiters_page(request):
    # Get the top 10 recruiters of all time to display
    top_recruiters = get_top_recruiters(request, limit=10)
    
    # Get the featured recruiter for the monthly highlight
    # Use the same logic as featured_recruiter_view to determine the featured one
    current_month_recruiters = get_top_recruiters_of_the_month(request, limit=1)
    if current_month_recruiters:
        featured_recruiter_data = current_month_recruiters[0]
        is_current_month = True
    else:
        all_time_recruiters = get_top_recruiters(request, limit=1)
        featured_recruiter_data = all_time_recruiters[0] if all_time_recruiters else None
        is_current_month = False
        
    context = {
        'top_recruiters': top_recruiters,
        'page_title': "Recruiters and Company Partners",
        'featured_recruiter': featured_recruiter_data,
        'is_current_month': is_current_month,
    }
    return render(request, 'sponsor.html', context)


# NEW VIEW: User Profile Page
@login_required
def user_profile(request):
    """
    Displays the current user's profile and their activities.
    Activities include job posts and products listed for sale.
    """
    username = request.user.username
    
    # 1. Recruiting (Job Posts) Activity
    # Assuming recruiter_name is used to identify the user's posts
    job_posts = JobPost.objects.filter(recruiter_name=username).order_by('-timestamp')

    # 2. Selling Items (Products Listed) Activity
    # Assuming vendor_name is used to identify the user's products
    # Will only query if the Product model import was successful
    if Product.objects is not None:
        products_listed = Product.objects.filter(vendor_name=username).order_by('-id')
    else:
        products_listed = []

    context = {
        'user': request.user,
        'job_posts': job_posts,
        'products_listed': products_listed,
        'page_title': f"Profile: {username}",
    }
    return render(request, 'user_profile.html', context)


# ... (other imports)

# ... (user_login view code)

def user_logout(request):
    """Logs the user out and redirects to the login page."""
    # Use Django's built-in logout function
    logout(request)
    # Optional: Display a success message
    messages.info(request, "You have been logged out successfully.")
    # Redirect to the login page or homepage
    return redirect(reverse('user_login'))
    
# ... (user_profile view code)    
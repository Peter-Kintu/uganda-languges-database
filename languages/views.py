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
import requests
import os
# The import 'from users.models import Profile' has been removed to fix the ImportError.

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

# languages/views.py

# ... existing code ...


def job_post_detail(request, pk):
    """
    Displays the details of a single job post.
    """
    job_post = get_object_or_404(JobPost, pk=pk)
    # TODO: Add logic for comments, related jobs, etc.
    context = {
        'job_post': job_post,
        'page_title': f"Job: {job_post.post_content[:40]}...",
    }
    return render(request, 'job_post_detail.html', context)


# Renamed get_top_contributors to get_top_recruiters
@login_required
def get_top_recruiters(request, month=None, year=None, limit=10):
    """
    A helper function to find and count top recruiters (contributors).
    Returns a list of dicts: [{'recruiter_name': 'Name', 'post_count': X}].
    If month/year are provided, filters by that period.
    """
    
    # Start with all validated posts
    posts = JobPost.objects.all()
    
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
    validated_posts = JobPost.objects.all().values(
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
                recruiter_name=recruiter_name,
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


# Environment Variables
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
CAREERJET_API_KEY = os.getenv("CAREERJET_API_KEY")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY") # Optional: For currency conversion

def get_exchange_rate(from_curr, to_curr="UGX"):
    """Helper to fetch live exchange rates."""
    if not EXCHANGE_RATE_API_KEY or from_curr == to_curr:
        return 1.0
    try:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/pair/{from_curr}/{to_curr}"
        res = requests.get(url, timeout=2)
        return res.json().get('conversion_rate', 1.0) if res.status_code == 200 else 1.0
    except:
        return 1.0

@login_required
def browse_job_listings(request):
    job_id = request.GET.get('job_id')
    selected_job = None
    
    if job_id:
        try:
            selected_job = get_object_or_404(JobPost, pk=job_id)
        except (ValueError, JobPost.DoesNotExist):
            pass 

    adzuna_jobs = []
    careerjet_jobs = []

    if selected_job is None:
        category_filter = request.GET.get('category')
        # Improved defaults to avoid "Software Only" bias
        search_query = request.GET.get('q') or "hiring" 
        location_query = request.GET.get('where') or "Africa"
        page = request.GET.get('page', 1)

        # A. LOCAL DATABASE SEARCH
        job_posts_filtered = JobPost.objects.all().order_by('-timestamp')
        
        if category_filter and category_filter != 'all':
            job_posts_filtered = job_posts_filtered.filter(job_category=category_filter)
            
        if search_query and search_query != "hiring":
            job_posts_filtered = job_posts_filtered.filter(
                Q(post_content__icontains=search_query) |
                Q(recruiter_name__icontains=search_query) |
                Q(recruiter_location__icontains=location_query)
            )
        final_job_list = list(job_posts_filtered)

        # B. EXTERNAL API BACKFILL (African & High-Paying Global Markets)
        if str(page) == '1':
            # 1. Expanded Country Mapping
            adzuna_country_map = {
                # High Paying
                'usa': 'us', 'united states': 'us', 'canada': 'ca', 
                'uae': 'ae', 'dubai': 'ae', 'uk': 'gb', 'germany': 'de',
                # African Hubs
                'south africa': 'za', 'nigeria': 'ng', 'kenya': 'ke', 
                'uganda': 'ug', 'egypt': 'eg', 'morocco': 'ma', 'ghana': 'gh'
            }
            
            loc_lower = location_query.lower()
            adzuna_code = 'za' # Default African hub
            for country, code in adzuna_country_map.items():
                if country in loc_lower:
                    adzuna_code = code
                    break

            # 2. Adzuna Integration
            if ADZUNA_APP_ID and ADZUNA_APP_KEY:
                try:
                    adzuna_url = f"https://api.adzuna.com/v1/api/jobs/{adzuna_code}/search/1"
                    adzuna_params = {
                        "app_id": ADZUNA_APP_ID,
                        "app_key": ADZUNA_APP_KEY,
                        "results_per_page": 20,
                        "what": search_query,
                        "where": location_query if adzuna_code not in ['us', 'ca', 'ae'] else "",
                        "content-type": "application/json"
                    }
                    # Exclude OfferZen to avoid the developer-only signup walls you saw earlier
                    if search_query == "hiring":
                        adzuna_params["what_exclude"] = "offerzen"

                    response = requests.get(adzuna_url, params=adzuna_params, timeout=5)
                    if response.status_code == 200:
                        adzuna_jobs = response.json().get('results', [])
                except Exception as e:
                    print(f"Adzuna API Error: {e}")

            # 3. Careerjet Integration (Global Locales)
            if CAREERJET_API_KEY:
                try:
                    # Switch locale based on country
                    locale = 'en_GB'
                    if 'usa' in loc_lower: locale = 'en_US'
                    elif 'canada' in loc_lower: locale = 'en_CA'
                    elif 'uae' in loc_lower or 'dubai' in loc_lower: locale = 'en_AE'
                    elif 'south africa' in loc_lower: locale = 'en_ZA'

                    cj_params = {
                        'locale_code': locale,
                        'keywords': search_query,
                        'location': location_query,
                        'user_ip': request.META.get('REMOTE_ADDR', '1.1.1.1'),
                        'user_agent': request.META.get('HTTP_USER_AGENT', 'Mozilla/5.0'),
                        'page_size': 20,
                    }

                    cj_res = requests.get('https://search.api.careerjet.net/v4/query', 
                                         params=cj_params, auth=(CAREERJET_API_KEY, ''), timeout=5)
                    if cj_res.status_code == 200:
                        cj_data = cj_res.json()
                        if cj_data.get('type') == 'JOBS':
                            careerjet_jobs = cj_data.get('jobs', [])
                except Exception as e:
                    print(f"Careerjet API Error: {e}")

        # C. LOCAL PAGINATION
        paginator = Paginator(final_job_list, 20)
        try:
            posts_on_page = paginator.page(page)
        except (PageNotAnInteger, EmptyPage):
            posts_on_page = paginator.page(1)
        job_posts_context = posts_on_page
    
    else:
        job_posts_context = []
        category_filter = request.GET.get('category')
        search_query = request.GET.get('q')
        location_query = request.GET.get('where')

    context = {
        'selected_job': selected_job,
        'job_posts': job_posts_context,
        'adzuna_jobs': adzuna_jobs, 
        'careerjet_jobs': careerjet_jobs,
        'job_categories': JOB_CATEGORIES, 
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query if search_query != "hiring" else '',
        'location_query': location_query,
        'page_title': f"Jobs in {location_query}"
    }
    return render(request, 'contributions_list.html', context)

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
    return redirect(reverse('users:user_login'))
    
# ... (user_profile view code)
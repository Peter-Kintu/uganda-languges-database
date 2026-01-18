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

# View for browsing and searching job listings (was: 'browse')
# @login_required
# def browse_job_listings(request):
#     # 1. Check for job detail request
#     job_id = request.GET.get('job_id')
#     selected_job = None
    
#     if job_id:
#         try:
#             # Fetch the specific job details if requested
#             selected_job = get_object_or_404(JobPost, pk=job_id)
#             # If a job is selected, we only need to render the detail view
#             # and can skip the complex list/pagination logic.
#         except ValueError:
#             # Handle non-integer job_id values gracefully
#             pass 

#     # --- Only proceed with list/filter/pagination logic if no job is selected ---
#     if selected_job is None:
        # Get filters from the request
        # category_filter = request.GET.get('category')
        # search_query = request.GET.get('q')
        # page = request.GET.get('page') # Get the page number

        # # Start with all validated posts, ordered by recency
        # all_job_posts = JobPost.objects.all().order_by('-timestamp')
        
        # # Apply category and search filters to the *entire* list before ranking
        # job_posts_filtered = all_job_posts
        
        # # 1. Apply category filter
        # if category_filter and category_filter != 'all':
        #     job_posts_filtered = job_posts_filtered.filter(job_category=category_filter)
            
        # # 2. Apply search filter
        # if search_query:
            # Search across post_content (job description), required_skills, and recruiter_name
        #     job_posts_filtered = job_posts_filtered.filter(
        #         Q(post_content__icontains=search_query) |
        #         Q(required_skills__icontains=search_query) |
        #         Q(recruiter_name__icontains=search_query)
        #     )

        # # --- 3. Recommendation Logic (Prioritization) ---
        # recommended_jobs = JobPost.objects.none() # Initialize an empty queryset

        # if request.user.is_authenticated:
        #     try:
        #         # We try to access the related profile object using the most common related names:
        #         user_profile = getattr(request.user, 'userprofile', None)
        #         if user_profile is None:
        #             user_profile = getattr(request.user, 'profile', None)
                
        #         # If a profile object was successfully retrieved
        #         if user_profile and hasattr(user_profile, 'skills'):
        #             user_skills_raw = user_profile.skills.split(',') if user_profile.skills else []
        #             # Clean and lower-case the skills for matching
        #             user_skills = [s.strip().lower() for s in user_skills_raw if s.strip()]
        #         else:
        #             user_skills = []
      
    
    
                    
            # except Exception:
            #     # Catch all exceptions during profile access to prevent a crash
            #     user_skills = []

            # if user_skills:
            #     # Build a Q object for jobs where required_skills field contains any of the user's skills
            #     skill_match_query = Q()
            #     for skill in user_skills:
            #         # Use Q(required_skills__icontains=skill) for case-insensitive partial match
            #         skill_match_query |= Q(required_skills__icontains=skill)

            #     # Separate recommended jobs from the filtered set
            #     recommended_jobs = job_posts_filtered.filter(skill_match_query).distinct()
                
            #     # Identify other jobs that were filtered but didn't match skills (or haven't been recommended)
            #     other_jobs = job_posts_filtered.exclude(pk__in=recommended_jobs.values_list('pk', flat=True))
                
            #     # Combine the two QuerySets: Recommended first, then others, maintaining order by timestamp
            #     final_job_list = list(recommended_jobs.order_by('-timestamp')) + list(other_jobs.order_by('-timestamp'))
                
            # else:
            #     # User is logged in but has no skills listed in their profile
            #     final_job_list = list(job_posts_filtered)
                
        # else:
        #     # User is not logged in
        #     final_job_list = list(job_posts_filtered)
            
        # # --- 4. Pagination setup ---
        # paginator = Paginator(final_job_list, 10) # Show 10 posts per page
        
        # try:
        #     posts_on_page = paginator.page(page)
        # except PageNotAnInteger:
        #     posts_on_page = paginator.page(1)
        # except EmptyPage:
        #     posts_on_page = paginator.page(paginator.num_pages)

        # # FIX: posts_on_page.object_list is a Python list, so we must manually extract pks
        # posts_pk_list = [job.pk for job in posts_on_page.object_list]
        
        # # Set list context variables
        # job_posts_context = posts_on_page
        # recommended_jobs_count_context = recommended_jobs.count()
        # is_recommended_page_context = True if recommended_jobs.filter(pk__in=posts_pk_list).exists() and posts_on_page.number == 1 else False
        # category_filter = request.GET.get('category')
        # search_query = request.GET.get('q')

    # else:
    #     # If a job is selected, use placeholder/defaults for list-only variables
    #     job_posts_context = []
    #     recommended_jobs_count_context = 0
    #     is_recommended_page_context = False
    #     category_filter = request.GET.get('category')
    #     search_query = request.GET.get('q')

    # context = {
    #     'selected_job': selected_job, # <--- CRITICAL FOR DETAIL VIEW
        
    #     'job_posts': job_posts_context, # Paginated list containing recommended and other jobs
    #     # Pass these for separate display in the template
    #     'recommended_jobs_count': recommended_jobs_count_context, 
    #     'is_recommended_page': is_recommended_page_context,
        
    #     'job_categories': JOB_CATEGORIES, 
    #     'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
    #     'search_query': search_query or '',
    #     'page_title': "Job Listings"
    # }
    
    # # If selected_job is present, update the page title for the detail view
    # if selected_job:
    #     context['page_title'] = f"Job: {selected_job.post_content[:40]}..."
        
    # return render(request, 'contributions_list.html', context)


# View for handling upvotes (was: 'like_phrase')

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
CAREERJET_API_KEY = os.getenv("CAREERJET_API_KEY")

@login_required
def browse_job_listings(request):
    """
    View for browsing and searching job listings across Africa. 
    Integrates local database results with dynamic external API backfills.
    """
    # 1. Handle single job detail view request
    job_id = request.GET.get('job_id')
    selected_job = None
    
    if job_id:
        try:
            selected_job = get_object_or_404(JobPost, pk=job_id)
        except (ValueError, JobPost.DoesNotExist):
            pass 

    adzuna_jobs = []
    careerjet_jobs = []

    # 2. Handle list view and search logic
    if selected_job is None:
        category_filter = request.GET.get('category')
        search_query = request.GET.get('q') or "jobs" 
        location_query = request.GET.get('where') or "Africa"
        page = request.GET.get('page', 1)

        # A. LOCAL DATABASE SEARCH
        job_posts_filtered = JobPost.objects.all().order_by('-timestamp')
        
        if category_filter and category_filter != 'all':
            job_posts_filtered = job_posts_filtered.filter(job_category=category_filter)
            
        if search_query and search_query != "jobs":
            job_posts_filtered = job_posts_filtered.filter(
                Q(post_content__icontains=search_query) |
                Q(recruiter_name__icontains=search_query) |
                Q(recruiter_location__icontains=location_query)
            )

        final_job_list = list(job_posts_filtered)

        # B. EXTERNAL API BACKFILL (Optimized for African Countries)
        if str(page) == '1':
            # --- Adzuna Country Mapping ---
            # Adzuna uses specific subdomains for different African countries
            adzuna_country_map = {
                'south africa': 'za',
                'nigeria': 'ng',
                'kenya': 'ke',
                'uganda': 'ug',
                'egypt': 'eg',
                'morocco': 'ma'
            }
            
            # Default to 'za' (South Africa) if searching 'Africa' generally, 
            # otherwise match the user input to a supported country code.
            loc_lower = location_query.lower()
            adzuna_code = 'za' # Global fallback for the continent
            for country, code in adzuna_country_map.items():
                if country in loc_lower:
                    adzuna_code = code
                    break

            # 1. Adzuna Integration
            if ADZUNA_APP_ID and ADZUNA_APP_KEY:
                try:
                    adzuna_url = f"https://api.adzuna.com/v1/api/jobs/{adzuna_code}/search/1"
                    adzuna_params = {
                        "app_id": ADZUNA_APP_ID,
                        "app_key": ADZUNA_APP_KEY,
                        "results_per_page": 50,
                        "what": search_query,
                        "where": location_query if adzuna_code != 'za' or 'south africa' in loc_lower else "",
                        "content-type": "application/json"
                    }
                    response = requests.get(adzuna_url, params=adzuna_params, timeout=5)
                    if response.status_code == 200:
                        adzuna_jobs = response.json().get('results', [])
                except Exception as e:
                    print(f"Adzuna API Error: {e}")

            # 2. Careerjet Integration (Pan-African Locale Support)
            if CAREERJET_API_KEY:
                try:
                    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
                    user_ip = x_forwarded.split(',')[0] if x_forwarded else request.META.get('REMOTE_ADDR', '1.1.1.1')
                    user_agent = request.META.get('HTTP_USER_AGENT', 'Mozilla/5.0')

                    # Careerjet uses locales. en_GB is a good fallback for most English-speaking Africa.
                    # We switch to fr_MA for francophone North Africa if detected.
                    locale = 'en_GB'
                    if any(x in loc_lower for x in ['morocco', 'algeria', 'tunisia', 'french']):
                        locale = 'fr_MA'

                    cj_params = {
                        'locale_code': locale,
                        'keywords': search_query,
                        'location': location_query,
                        'user_ip': user_ip,
                        'user_agent': user_agent,
                        'page_size': 50,
                    }

                    cj_response = requests.get(
                        'https://search.api.careerjet.net/v4/query',
                        params=cj_params,
                        auth=(CAREERJET_API_KEY, ''),
                        headers={'Referer': request.build_absolute_uri()},
                        timeout=5
                    )
                    if cj_response.status_code == 200:
                        cj_data = cj_response.json()
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
        # Defaults for Detail View
        job_posts_context = []
        category_filter = request.GET.get('category')
        search_query = request.GET.get('q')
        location_query = request.GET.get('where')

    # 3. CONTEXT FOR TEMPLATE
    context = {
        'selected_job': selected_job,
        'job_posts': job_posts_context,
        'adzuna_jobs': adzuna_jobs, 
        'careerjet_jobs': careerjet_jobs,
        'job_categories': JOB_CATEGORIES, 
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query if search_query != "jobs" else '',
        'location_query': location_query,
        'page_title': f"Jobs in {location_query}: {search_query}" if not selected_job else f"Job: {selected_job.post_content[:50]}..."
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
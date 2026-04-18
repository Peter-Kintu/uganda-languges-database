from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Count
from django.urls import reverse
from datetime import date, datetime, timedelta
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from django.conf import settings
import requests
import os
import re

from .forms import JobPostForm
from .models import JobPost, JOB_CATEGORIES, JOB_TYPES, Applicant 

try:
    from eshop.models import Product 
except ImportError:
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

def job_post_detail(request, pk):
    job_post = get_object_or_404(JobPost, pk=pk)
    context = {
        'job_post': job_post,
        'page_title': f"Job: {job_post.post_content[:40]}...",
    }
    return render(request, 'job_post_detail.html', context)

@login_required
def get_top_recruiters(request, month=None, year=None, limit=10):
    posts = JobPost.objects.all()
    if month is not None and year is not None:
        posts = posts.filter(timestamp__month=month, timestamp__year=year)
    top_recruiters = posts.values('recruiter_name') \
        .annotate(post_count=Count('recruiter_name')) \
        .order_by('-post_count')[:limit]
    return list(top_recruiters)

@login_required
def get_top_recruiters_of_the_month(request, limit=10):
    now = date.today()
    return get_top_recruiters(request, month=now.month, year=now.year, limit=limit)

@login_required
def featured_recruiter_view(request):
    featured_recruiter_data = None
    is_current_month = False
    current_month_recruiters = get_top_recruiters_of_the_month(request, limit=1)
    
    if current_month_recruiters:
        featured_recruiter_data = current_month_recruiters[0]
        is_current_month = True
    else:
        all_time_recruiters = get_top_recruiters(request, limit=1)
        featured_recruiter_data = all_time_recruiters[0] if all_time_recruiters else None
        is_current_month = False

    context = {}
    if featured_recruiter_data:
        context['recruiter_name'] = featured_recruiter_data['recruiter_name']
        context['post_count'] = featured_recruiter_data['post_count']
        context['is_current_month'] = is_current_month
    else:
        context['recruiter_name'] = "No Featured Recruiter Yet"
        context['post_count'] = 0
        context['is_current_month'] = True

    return render(request, 'best_contributor.html', context)

@login_required
def export_contributions_json(request):
    validated_posts = JobPost.objects.all().values(
        'post_content', 'required_skills', 'job_category', 
        'job_type', 'recruiter_name', 'recruiter_location',
        'timestamp', 'company_logo_or_media'
    )
    data = list(validated_posts)
    response = JsonResponse(data, safe=False)
    response['Content-Disposition'] = 'attachment; filename="validated_job_posts.json"'
    return response

@login_required
def post_job(request):
    if request.method == 'POST':
        form = JobPostForm(request.POST, request.FILES) 
        if form.is_valid():
            job_post = form.save(commit=False)
            recruiter_name = job_post.recruiter_name
            applicant, created = Applicant.objects.get_or_create(
                recruiter_name=recruiter_name,
                defaults={'location': job_post.recruiter_location} 
            )
            job_post.applicant = applicant
            job_post.save()
            job_post.applicant.total_posts = job_post.applicant.jobpost_set.count()
            job_post.applicant.save()
            return redirect(reverse('languages:browse_job_listings'))
    else:
        form = JobPostForm()
    return render(request, 'contribute.html', {'form': form})

# API Credentials
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
CAREERJET_API_KEY = os.getenv("CAREERJET_API_KEY")
# Ensure the publisher ID falls back to the API key if not specifically set
CAREERJET_PUBLISHER_ID = os.getenv("CAREERJET_PUBLISHER_ID") or CAREERJET_API_KEY
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

# Cache so you don't burn API limits
cache = {"adzuna": {"data": [], "expires": datetime.now()},
         "careerjet": {"data": [], "expires": datetime.now()}}

BAD_TITLE_KEYWORDS = [
    'we are hiring', 'hiring!', 'job opportunity', 'vacancy', 'apply now',
    'urgent', 'staff needed', 'is for hiring', 'job alert'
]
BAD_TITLES_EXACT = ['hiring', 'we are hiring', 'is for hiring', 'jobs']

def clean_adzuna_job(job):
    """Returns job with clean_title or None if job is garbage"""
    title = job.get('title', '').strip()
    company = job.get('company', {}).get('display_name', '').strip()
    location = job.get('location', {}).get('display_name', '')
    description = job.get('description', '')
    salary_min = job.get('salary_min')

    # Rule 1: Drop garbage titles
    if title.lower() in BAD_TITLES_EXACT:
        return None
    if any(bad in title.lower() for bad in BAD_TITLE_KEYWORDS):
        # Try salvage from description first line
        first_line = description.split('\n')[0][:80].strip()
        if len(first_line) > 10 and not any(bad in first_line.lower() for bad in BAD_TITLE_KEYWORDS):
            title = first_line
        else:
            return None

    # Rule 2: Must have company + specific location. "Uganda" alone = spam
    if not company or not location or location.lower() == 'uganda':
        return None

    # Rule 3: Clean the title
    title = re.sub(r'\b(Hiring|Apply|Urgent|Now|!|Vacancy)\b', '', title, flags=re.I).strip()
    title = re.sub(r'\s+', ' ', title)
    # Title case but keep IT, CEO, HR, etc
    title = ' '.join([w if w.isupper() and len(w) < 5 else w.capitalize() for w in title.split()])

    # Add company if title too short
    if len(title) < 18 and company:
        title = f"{title} - {company}"

    if len(title) > 65:
        title = title[:62] + '...'

    if len(title) < 8: # Still bad after cleaning
        return None

    job['clean_title'] = title
    job['display_salary'] = f"UGX {int(salary_min):,}/mo" if salary_min else None
    return job

def get_adzuna_jobs(q="", where="Kampala"):
    if cache["adzuna"]["data"] and cache["adzuna"]["expires"] > datetime.now():
        return cache["adzuna"]["data"]

    url = f"https://api.adzuna.com/v1/api/jobs/ug/search/1"
    params = {
        "app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY,
        "results_per_page": 30, "what": q, "where": where,
        "sort_by": "relevance"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        raw_jobs = r.json().get("results", [])
        cleaned = []
        seen = set()
        for job in raw_jobs:
            clean_job = clean_adzuna_job(job)
            if clean_job:
                key = f"{clean_job['clean_title']}-{clean_job['company']['display_name']}"
                if key not in seen: # dedupe
                    seen.add(key)
                    cleaned.append(clean_job)
        cache["adzuna"]["data"] = cleaned
        cache["adzuna"]["expires"] = datetime.now() + timedelta(minutes=15)
        return cleaned
    except:
        return []

def is_careerjet_sponsored(job):
    """CareerJet sponsored jobs have tracking params. Free jobs = direct company link"""
    url = job.get('url', '')
    company = job.get('company', '').strip()
    # Sponsored = has affid, click, rc, or comes from careerjet redirect domain
    sponsored_patterns = ['affid=', 'click', 'rc=', 'source=', 'careerjet.com/click']
    has_tracking = any(p in url for p in sponsored_patterns)
    has_company = len(company) > 1
    return has_tracking and has_company

def get_careerjet_jobs(q="", location="Kampala"):
    if cache["careerjet"]["data"] and cache["careerjet"]["expires"] > datetime.now():
        return cache["careerjet"]["data"]

    url = "https://public.api.careerjet.net/search"
    params = {
        "affid": CAREERJET_PUBLISHER_ID,
        "keywords": q,
        "location": location,
        "pagesize": 50,
        "page": 1,
        "sort": "relevance"
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        raw_jobs = r.json().get("jobs", [])
        # Only keep sponsored that pay you
        sponsored = [job for job in raw_jobs if is_careerjet_sponsored(job)]
        cache["careerjet"]["data"] = sponsored
        cache["careerjet"]["expires"] = datetime.now() + timedelta(minutes=15)
        return sponsored
    except:
        return []

def get_exchange_rate(from_curr, to_curr="UGX"):
    if not EXCHANGE_RATE_API_KEY or from_curr == to_curr:
        return 1.0
    try:
        url = f"https://v6.exchangerate-api.com/v6/{EXCHANGE_RATE_API_KEY}/pair/{from_curr}/{to_curr}"
        res = requests.get(url, timeout=2)
        return res.json().get('conversion_rate', 1.0) if res.status_code == 200 else 1.0
    except:
        return 1.0

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

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

    category_filter = request.GET.get('category')
    search_query = request.GET.get('q') or "hiring" 
    location_query = request.GET.get('where') or ""
    search_type = request.GET.get('search_type', 'api')
    page = request.GET.get('page', 1)

    display_query = search_query if search_query != "hiring" else "Freelance"
    solidgigs_data = {
        'name': f"Elite {display_query.title()} Roles",
        'url': f"https://solidgigs.com?via=kintu92",
        'query_used': display_query,
    }

    if selected_job is None:
        final_job_list = []
        
        # --- GLOBAL WEB CRAWL MODE ---
        if search_type == 'crawl' and search_query and search_query != "hiring":
            try:
                from jobspy import scrape_jobs
                print(f"Starting jobspy crawl for '{search_query}' in '{location_query}'...")
                
                scraped_df = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor"],
                    search_term=search_query,
                    location=location_query or "Uganda",
                    results_wanted=15,
                    hours_old=72,
                )
                
                # Convert scraped data to display format
                for _, row in scraped_df.iterrows():
                    job_url = row.get('job_url') or row.get('url')
                    if job_url:
                        final_job_list.append({
                            'post_content': row.get('title', search_query),
                            'required_skills': (row.get('description', '')[:200] if row.get('description') else "Click to view full job details"),
                            'recruiter_name': row.get('company', 'Global Employer'),
                            'recruiter_location': row.get('location', location_query or 'Remote'),
                            'application_url': job_url,
                            'is_external': True,
                            'external_source': 'jobspy',
                            'timestamp': row.get('date_posted'),
                            'upvotes': 0,
                        })
                
                print(f"Crawl complete: found {len(final_job_list)} jobs")
                
            except ImportError:
                messages.error(request, 'python-jobspy is not installed. Install with: pip install python-jobspy')
                final_job_list = []
            except Exception as e:
                print(f"Crawl error: {e}")
                messages.error(request, f"Global crawl failed: {str(e)}. Showing cached results instead.")
                final_job_list = []
        
        else:
            # --- STANDARD API & LOCAL SEARCH ---
            job_posts_filtered = JobPost.objects.all().order_by('-timestamp')
            job_posts_filtered = job_posts_filtered.filter(
                Q(is_external=False) | Q(external_source__in=['adzuna', 'careerjet', 'jobspy'])
            )

            if category_filter and category_filter != 'all':
                job_posts_filtered = job_posts_filtered.filter(job_category=category_filter)
            if search_query and search_query != "hiring":
                job_posts_filtered = job_posts_filtered.filter(
                    Q(post_content__icontains=search_query) |
                    Q(recruiter_name__icontains=search_query) |
                    Q(recruiter_location__icontains=location_query)
                )
            final_job_list = list(job_posts_filtered)

        loc_lower = location_query.lower()
        
        # Only fetch from APIs if NOT in crawl mode
        if search_type != 'crawl':
            adzuna_jobs = get_adzuna_jobs(q=search_query, where=location_query)
            careerjet_jobs = get_careerjet_jobs(q=search_query, location=location_query)

        paginator = Paginator(final_job_list, 20)
        posts_on_page = paginator.get_page(page)
        job_posts_context = posts_on_page
    
    else:
        job_posts_context = []

    context = {
        'selected_job': selected_job,
        'job_posts': job_posts_context,
        'adzuna_jobs': adzuna_jobs, 
        'careerjet_jobs': careerjet_jobs,
        'solidgigs': solidgigs_data,
        'job_categories': JOB_CATEGORIES, 
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query if search_query != "hiring" else '',
        'location_query': location_query,
        'search_type': search_type,
        'page_title': f"Jobs in {location_query}",
        # Keep variable for template filter fallback
        'CAREERJET_API_KEY': CAREERJET_PUBLISHER_ID,
    }
    return render(request, 'contributions_list.html', context)

@require_POST
@login_required
def upvote_job_application(request, pk):
    job_post = get_object_or_404(JobPost, pk=pk)
    job_post.upvotes = F('upvotes') + 1
    job_post.save(update_fields=['upvotes'])
    job_post.refresh_from_db()
    return JsonResponse({'success': True, 'new_upvotes': job_post.upvotes})

@login_required
def recruiters_page(request):
    top_recruiters = get_top_recruiters(request, limit=10)
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

@login_required
def user_profile(request):
    username = request.user.username
    job_posts = JobPost.objects.filter(recruiter_name=username).order_by('-timestamp')
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

def user_logout(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect(reverse('users:user_login'))
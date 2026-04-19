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
import json
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
JOOBLE_API_KEY = os.getenv("JOOBLE_API_KEY") or "46f60849-92b7-4a9f-a381-709376fe6f92"
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

BAD_TITLE_KEYWORDS = [
    'we are hiring', 'hiring!', 'job opportunity', 'vacancy', 'apply now',
    'urgent', 'staff needed', 'is for hiring', 'job alert', 'job opening',
    'career opportunity', 'join our team', 'work with us', 'employment opportunity'
]
BAD_TITLES_EXACT = ['hiring', 'we are hiring', 'is for hiring', 'jobs', 'job', 'vacancies', 'careers', 'vacancy']

def fetch_jooble_data(keywords, location="Uganda"):
    api_key = JOOBLE_API_KEY
    url = f"https://jooble.org/api/{api_key}"
    headers = {"Content-Type": "application/json"}
    body = {
        "keywords": keywords,
        "location": location or "Uganda",
        "radius": "25",
        "page": "1",
    }
    try:
        response = requests.post(url, data=json.dumps(body), headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data.get("jobs", [])
    except Exception as e:
        print(f"Jooble API Connection Error: {e}")
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

    external_jobs = []

    category_filter = request.GET.get('category')
    search_query = request.GET.get('q') or ""
    location_query = request.GET.get('where') or "Uganda"
    search_type = request.GET.get('search_type', 'api')
    page = request.GET.get('page', 1)

    display_query = search_query if search_query else "Freelance"
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
            job_posts_filtered = JobPost.objects.filter(is_validated=True).order_by('-timestamp')

            if category_filter and category_filter != 'all':
                job_posts_filtered = job_posts_filtered.filter(job_category=category_filter)
            if search_query:
                job_posts_filtered = job_posts_filtered.filter(
                    Q(post_content__icontains=search_query) |
                    Q(required_skills__icontains=search_query) |
                    Q(recruiter_name__icontains=search_query)
                )
            final_job_list = list(job_posts_filtered)

        # Only fetch Jooble results when a search or location is active
        if search_type != 'crawl' and (search_query or location_query):
            external_jobs = fetch_jooble_data(search_query or 'jobs', location_query)

        paginator = Paginator(final_job_list, 20)
        posts_on_page = paginator.get_page(page)
        job_posts_context = posts_on_page
    
    else:
        job_posts_context = []

    context = {
        'selected_job': selected_job,
        'job_posts': job_posts_context,
        'external_jobs': external_jobs,
        'solidgigs': solidgigs_data,
        'job_categories': JOB_CATEGORIES, 
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query,
        'location_query': location_query,
        'search_type': search_type,
        'page_title': f"Jobs in {location_query}",
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
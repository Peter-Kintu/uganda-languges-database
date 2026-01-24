from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.db.models import F, Q, Count
from django.urls import reverse
from datetime import date
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
import requests
import os

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

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY")
CAREERJET_API_KEY = os.getenv("CAREERJET_API_KEY")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

def get_exchange_rate(from_curr, to_curr="UGX"):
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

    category_filter = request.GET.get('category')
    search_query = request.GET.get('q') or "hiring" 
    location_query = request.GET.get('where') or "Africa"
    page = request.GET.get('page', 1)

    # --- SOLIDGIGS PARTNER DATA ---
    display_query = search_query if search_query != "hiring" else "Freelance"
    solidgigs_data = {
        'name': f"Elite {display_query.title()} Roles",
        'url': f"https://solidgigs.com?via=kintu92",
        'query_used': display_query,
    }

    if selected_job is None:
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

        # B. EXTERNAL API BACKFILL
        loc_lower = location_query.lower()
        
        # --- 1. Adzuna Integration ---
        adzuna_country_map = {
            'south africa': 'za', 'nigeria': 'ng', 'kenya': 'ke', 
            'uganda': 'ug', 'egypt': 'eg', 'morocco': 'ma',
            'ghana': 'gh', 'ivory coast': 'ci', 'tanzania': 'tz',
            'usa': 'us', 'uk': 'gb', 'uae': 'ae'
        }
        
        adzuna_code = 'za' 
        for country, code in adzuna_country_map.items():
            if country in loc_lower:
                adzuna_code = code
                break

        if ADZUNA_APP_ID and ADZUNA_APP_KEY:
            try:
                adzuna_url = f"https://api.adzuna.com/v1/api/jobs/{adzuna_code}/search/{page}"
                adzuna_params = {
                    "app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY,
                    "results_per_page": 15, "what": search_query,
                    "where": location_query if adzuna_code not in ['us', 'gb'] else "",
                    "content-type": "application/json"
                }
                res = requests.get(adzuna_url, params=adzuna_params, timeout=5)
                if res.status_code == 200:
                    adzuna_jobs = res.json().get('results', [])
            except: pass

        # --- 2. Careerjet Integration ---
        if CAREERJET_API_KEY:
            cj_locale = 'en_GB' 
            if 'uganda' in loc_lower: cj_locale = 'en_UG'
            elif 'kenya' in loc_lower: cj_locale = 'en_KE'
            elif 'nigeria' in loc_lower: cj_locale = 'en_NG'
            elif 'south africa' in loc_lower: cj_locale = 'en_ZA'
            elif 'ghana' in loc_lower: cj_locale = 'en_GH'
            elif 'ethiopia' in loc_lower: cj_locale = 'en_ET'
            elif 'rwanda' in loc_lower: cj_locale = 'en_RW'
            elif 'tanzania' in loc_lower: cj_locale = 'en_TZ'
            elif 'usa' in loc_lower: cj_locale = 'en_US'
            elif 'africa' in loc_lower: cj_locale = 'en_ZA'

            try:
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    u_ip = x_forwarded_for.split(',')[0].strip()
                else:
                    u_ip = request.META.get('REMOTE_ADDR')
                
                u_agent = request.META.get('HTTP_USER_AGENT', 'Mozilla/5.0')
                search_loc = "" if "africa" in loc_lower else location_query

                cj_params = {
                    'locale_code': cj_locale,
                    'keywords': search_query if search_query != "hiring" else "",
                    'location': search_loc,
                    'user_ip': u_ip,
                    'user_agent': u_agent,
                    'page_size': 25,
                    'page': page,
                }

                cj_headers = {'Referer': 'https://initial-danette-africana-60541726.koyeb.app'}

                cj_res = requests.get(
                    'https://search.api.careerjet.net/v4/query', 
                    params=cj_params, 
                    auth=(CAREERJET_API_KEY, ''), 
                    headers=cj_headers, 
                    timeout=5
                )
                
                if cj_res.status_code == 200:
                    cj_data = cj_res.json()
                    if cj_data.get('type') == 'JOBS':
                        careerjet_jobs = cj_data.get('jobs', [])
                    
                    if not careerjet_jobs:
                        cj_params['locale_code'] = 'en_US'
                        cj_params['location'] = "" 
                        retry = requests.get('https://search.api.careerjet.net/v4/query', 
                                           params=cj_params, auth=(CAREERJET_API_KEY, ''), 
                                           headers=cj_headers, timeout=5)
                        careerjet_jobs = retry.json().get('jobs', []) if retry.status_code == 200 else []

            except Exception as e:
                print(f"CJ Error: {e}")

        # Local Pagination
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
        'page_title': f"Jobs in {location_query}"
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
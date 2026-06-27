from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
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
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import os
import re
import base64
import time

from .forms import JobPostForm
from .models import JobPost, JOB_CATEGORIES, JOB_TYPES, Applicant 

try:
    from eshop.models import Product 
except ImportError:
    class Product:
        objects = None 

from functools import wraps
from django.views.decorators.http import condition
from django.utils.decorators import decorator_from_middleware_with_args


def allow_google_bot_or_login(view_func):
    """Bypasses auth for Google crawlers (AdSense / Googlebot) but enforces login for regular visitors."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        user_agent = (request.META.get('HTTP_USER_AGENT') or '').lower()
        
        # Google crawlers that need access to see ads
        google_crawlers = [
            'mediapartners-google',  # AdSense crawler
            'googlebot',              # Main Google crawler
            'google-site-verification',  # Google verification
            'adsbot-google',          # Google Ads crawler
            'bingbot',                # Bing crawler (also crawls for ads)
        ]
        
        is_google_crawler = any(crawler in user_agent for crawler in google_crawlers)
        
        # For Google crawlers, set cache headers to allow AdSense scanning
        if is_google_crawler:
            response = view_func(request, *args, **kwargs)
            # Allow crawlers to cache and re-crawl for ad verification
            response['Cache-Control'] = 'public, max-age=3600'
            response['X-Robots-Tag'] = 'index, follow'
            return response
        
        # enforce normal login for humans
        if not request.user.is_authenticated:
            return redirect('users:user_login')
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def google_verification(request):
    return HttpResponse("google-site-verification: googlec0826a61eabee54e.html")

def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow:",
        "Allow: /",
        "Allow: /go",
        "Allow: /go/",
        f"Sitemap: https://{settings.DEFAULT_DOMAIN}/sitemap.xml"
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
# Try both CAREERJET_PUBLISHER_ID and CAREERJET_API_KEY for compatibility
CAREERJET_API_KEY = os.getenv("CAREERJET_PUBLISHER_ID") or os.getenv("CAREERJET_API_KEY") or "a9927b4ab404ffaff0e637290f35b7a8"
CAREERJET_API_ENABLED = os.getenv("CAREERJET_ENABLED", "1").lower() in ("1", "true", "yes")
EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")

# Log API key status for debugging (first 6 chars only for security)
if CAREERJET_API_KEY:
    key_preview = CAREERJET_API_KEY[:6] + "..." if len(CAREERJET_API_KEY) > 6 else "****"
    print(f"[CareerJet] API Key loaded: {key_preview}")
else:
    print("[CareerJet] WARNING: No API key found!")

# Simple in-memory cache for API results (5 minutes)
api_cache = {}
CACHE_DURATION = 300  # 5 minutes

def get_cache_key(api_name, keywords, location):
    """Generate cache key for API results"""
    return f"{api_name}_{keywords}_{location}".lower().replace(" ", "_")

def get_cached_result(cache_key):
    """Get cached result if still valid"""
    if cache_key in api_cache:
        cached_time, data = api_cache[cache_key]
        if time.time() - cached_time < CACHE_DURATION:
            print(f"Cache hit for {cache_key}")
            return data
        else:
            # Remove expired cache
            del api_cache[cache_key]
    return None

def set_cache_result(cache_key, data):
    """Cache API result"""
    api_cache[cache_key] = (time.time(), data)
    print(f"Cached result for {cache_key}")


def normalize_search_location(location):
    """Normalize location input - accepts any location or empty for global"""
    if not location or not str(location).strip():
        return ""  # Empty means global search
    normalized = str(location).strip().lower()
    if normalized in ["world", "global", "all", "remote", "anywhere"]:
        return ""  # Treat as global
    # Return the original location as-is to support all countries and regions
    return str(location).strip()

BAD_TITLE_KEYWORDS = [
    'we are hiring', 'hiring!', 'job opportunity', 'vacancy', 'apply now',
    'urgent', 'staff needed', 'is for hiring', 'job alert', 'job opening',
    'career opportunity', 'join our team', 'work with us', 'employment opportunity'
]
BAD_TITLES_EXACT = ['hiring', 'we are hiring', 'is for hiring', 'jobs', 'job', 'vacancies', 'careers', 'vacancy']

MAX_JOB_AGE_DAYS = 10

def parse_job_date(raw_date):
    if not raw_date:
        return None
    if isinstance(raw_date, datetime):
        return raw_date
    if isinstance(raw_date, date):
        return datetime(raw_date.year, raw_date.month, raw_date.day)
    value = str(raw_date).strip()
    if not value:
        return None

    try:
        from dateutil import parser
        return parser.parse(value)
    except Exception:
        pass

    clean_value = value.replace('T', ' ').replace('Z', '').split('+')[0].split('Z')[0].strip()
    formats = [
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d',
        '%d %b %Y',
        '%d %B %Y',
        '%b %d, %Y',
        '%B %d, %Y',
    ]
    for fmt in formats:
        try:
            return datetime.strptime(clean_value, fmt)
        except Exception:
            continue
    return None


def is_recent_job(raw_date, max_age_days=MAX_JOB_AGE_DAYS):
    parsed = parse_job_date(raw_date)
    if not parsed:
        return True
    now = datetime.utcnow()
    try:
        age = now - parsed
    except TypeError:
        return True
    return age <= timedelta(days=max_age_days)


def fetch_jooble_data(keywords, location=""):
    """
    Fetch real-time jobs from Jooble API with global coverage.
    Supports jobs from all African countries and the rest of the world.
    """
    # Check cache first
    cache_key = get_cache_key("jooble", keywords or "jobs", location or "global")
    cached_result = get_cached_result(cache_key)
    if cached_result is not None:
        return cached_result

    api_key = JOOBLE_API_KEY
    url = f"https://jooble.org/api/{api_key}"

    # Simple API headers for third-party search requests
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "AfricanaAI-JobSearch/1.0",
        "Accept": "application/json",
    }

    # Clean and prepare search parameters
    normalized_location = normalize_search_location(location)
    api_location = normalized_location

    # Clean keywords - remove bad terms that trigger spam filters
    if keywords:
        keywords = keywords.strip()
        # Remove bad keywords that trigger spam detection
        for bad_word in BAD_TITLE_KEYWORDS + BAD_TITLES_EXACT:
            keywords = keywords.replace(bad_word, "").strip()

        # If keywords become empty after cleaning, use a generic term
        if not keywords or len(keywords) < 2:
            keywords = "jobs"
    else:
        keywords = "jobs"

    body = {
        "keywords": keywords,
        "location": api_location,
        "radius": "50",  # Increased radius for more results
        "page": "1",
    }

    # Add small delay to avoid rate limiting
    time.sleep(0.5)

    try:
        # Create session for better cookie handling and retry
        session = requests.Session()
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[403, 429, 500, 502, 503, 504], allowed_methods=["POST", "GET"])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(headers)

        print(f"Jooble: Searching '{keywords}' in '{api_location or 'Global'}'")

        response = session.post(url, json=body, timeout=15)

        print(f"Jooble Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            jobs = data.get("jobs", [])

            if not jobs and api_location:
                # Fallback to global search if location-specific fails
                print("Jooble: No location results, trying global search...")
                body["location"] = ""
                response = session.post(url, json=body, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    jobs = data.get("jobs", [])

            # Process and clean job data
            processed_jobs = []
            for job in jobs:
                # Skip jobs with bad titles
                title = job.get("title", "").lower()
                if any(bad in title for bad in BAD_TITLE_KEYWORDS) or title in BAD_TITLES_EXACT:
                    continue

                date_posted = job.get("updated", "") or job.get("date", "")
                if not is_recent_job(date_posted):
                    continue

                processed_job = {
                    "source": "Jooble",
                    "title": job.get("title", "Job Title"),
                    "company": job.get("company", "Company"),
                    "location": job.get("location", api_location or "Remote"),
                    "salary": job.get("salary", ""),
                    "description": job.get("snippet", "")[:300] + "..." if job.get("snippet") else "",
                    "link": job.get("link") or job.get("url", ""),
                    "date_posted": date_posted,
                }

                # Only add if we have a valid link
                if processed_job["link"] and processed_job["link"].startswith('http'):
                    processed_jobs.append(processed_job)

            print(f"Jooble: Found {len(processed_jobs)} valid jobs")

            # Cache the result
            set_cache_result(cache_key, processed_jobs)
            return processed_jobs

        elif response.status_code in (403, 429):
            print(f"Jooble: {response.status_code} blocked. Retrying with alternative headers...")
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            session.headers.update(headers)
            time.sleep(1.0)
            response = session.post(url, json=body, timeout=15)
            if response.status_code == 200:
                data = response.json()
                jobs = data.get("jobs", [])
                processed_jobs = []
                for job in jobs:
                    title = job.get("title", "").lower()
                    if any(bad in title for bad in BAD_TITLE_KEYWORDS) or title in BAD_TITLES_EXACT:
                        continue
                    processed_job = {
                        "source": "Jooble",
                        "title": job.get("title", "Job Title"),
                        "company": job.get("company", "Company"),
                        "location": job.get("location", api_location or "Remote"),
                        "salary": job.get("salary", ""),
                        "description": job.get("snippet", "")[:300] + "..." if job.get("snippet") else "",
                        "link": job.get("link") or job.get("url", ""),
                        "date_posted": job.get("updated", ""),
                    }
                    date_posted = job.get("updated", "") or job.get("date", "")
                    if not is_recent_job(date_posted):
                        continue

                    if processed_job["link"] and processed_job["link"].startswith('http'):
                        processed_jobs.append(processed_job)

                set_cache_result(cache_key, processed_jobs)
                return processed_jobs

        else:
            print(f"Jooble API Error: {response.status_code} - {response.text[:200]}")

    except requests.exceptions.Timeout:
        print("Jooble: Request timeout")
    except requests.exceptions.ConnectionError:
        print("Jooble: Connection error")
    except Exception as e:
        print(f"Jooble API Error: {e}")

    # Return empty list and cache it to avoid repeated failed requests
    empty_result = []
    set_cache_result(cache_key, empty_result)
    return empty_result


@require_GET
def job_redirect(request):
    job_url = request.GET.get('url')
    source = request.GET.get('source', 'unknown')
    print(f"External click: {source} -> {job_url}")

    if not job_url or not job_url.startswith('http'):
        return redirect('/')

    # Simple redirect for external job links
    return redirect(job_url)


def fetch_careerjet_data(request, keywords, location=""):
    """
    Fetch real-time jobs from CareerJet API with global coverage.
    Supports jobs from all African countries and the rest of the world.
    """
    if not CAREERJET_API_ENABLED:
        print("CareerJet: Disabled via environment variable CAREERJET_ENABLED")
        return []

    # Check cache first
    cache_key = get_cache_key("careerjet", keywords or "jobs", location or "global")
    cached_result = get_cached_result(cache_key)
    if cached_result is not None:
        return cached_result

    if not keywords:
        keywords = "jobs"

    # Use full keywords for better results
    search_keywords = keywords

    url = "https://search.api.careerjet.net/v4/query"

    # Get real user data for CareerJet required request metadata
    user_ip = get_client_ip(request) or request.META.get('REMOTE_ADDR', '127.0.0.1') or '127.0.0.1'
    user_agent = request.META.get('HTTP_USER_AGENT', '') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    referer = request.build_absolute_uri()

    normalized_location = normalize_search_location(location)

    # CareerJet requires user_ip and user_agent as query params
    params = {
        'locale_code': 'en_GB',
        'keywords': search_keywords,
        'location': normalized_location,  # Can be empty for global search
        'page_size': 30,
        'user_ip': user_ip,
        'user_agent': user_agent,
        'sort': 'date',
    }

    credentials = base64.b64encode(f"{CAREERJET_API_KEY}:".encode()).decode()

    headers = {
        'Authorization': f'Basic {credentials}',
        'Content-Type': 'application/json',
        'User-Agent': user_agent,
        'Accept': 'application/json',
        'Referer': referer,
    }

    display_location = normalized_location if normalized_location else 'Worldwide'
    print(f"CareerJet: Searching '{search_keywords}' in '{display_location}'")

    # Add small delay to avoid rate limiting
    time.sleep(0.5)

    try:
        # Use session for better connection handling
        session = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504], allowed_methods=["POST", "GET"])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(headers)

        response = session.get(url, params=params, timeout=20)
        print(f"CareerJet Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            response_type = data.get('type')

            if response_type == 'JOBS':
                jobs = data.get("jobs", [])
                print(f"CareerJet: Found {len(jobs)} jobs")

                processed_jobs = []
                for job in jobs:
                    # Skip jobs with bad titles
                    title = job.get("title", "").lower()
                    if any(bad in title for bad in BAD_TITLE_KEYWORDS) or title in BAD_TITLES_EXACT:
                        continue

                    job_location = job.get("locations", [display_location or "Remote"])
                    job_location = job_location[0] if job_location and isinstance(job_location, list) else job_location or "Remote"

                    date_posted = job.get("date", "") or job.get("updated", "")
                    if not is_recent_job(date_posted):
                        continue

                    processed_job = {
                        "source": "CareerJet",
                        "title": job.get("title", "Job Title"),
                        "company": job.get("company", "Company"),
                        "location": job_location,
                        "salary": job.get("salary", ""),
                        "description": job.get("description", "")[:300] + "..." if job.get("description") else "",
                        "link": job.get("url", ""),
                        "date_posted": date_posted,
                    }

                    # Only add if we have a valid link
                    if processed_job["link"] and processed_job["link"].startswith('http'):
                        processed_jobs.append(processed_job)

                print(f"CareerJet: Returning {len(processed_jobs)} valid jobs")
                set_cache_result(cache_key, processed_jobs)
                return processed_jobs

            elif response_type == 'LOCATIONS':
                # Location not found - try first matched CareerJet location then global search
                print(f"CareerJet: Location '{normalized_location}' not found - checking location suggestions")
                location_suggestions = data.get('locations') or data.get('results') or []
                if location_suggestions:
                    first_location = location_suggestions[0]
                    if isinstance(first_location, dict):
                        first_location = first_location.get('name') or first_location.get('location') or first_location.get('city') or ''
                    params['location'] = str(first_location).strip() if first_location else ''
                    print(f"CareerJet: Retrying using matched location '{params['location'] or 'Worldwide'}'")
                else:
                    params['location'] = ''

                time.sleep(0.5)
                response = session.get(url, params=params, timeout=20)

                if response.status_code == 200:
                    data = response.json()
                    if data.get('type') == 'JOBS':
                        jobs = data.get("jobs", [])
                        processed_jobs = []
                        for job in jobs:
                            title = job.get("title", "").lower()
                            if any(bad in title for bad in BAD_TITLE_KEYWORDS) or title in BAD_TITLES_EXACT:
                                continue

                            job_location = job.get("locations", ["Worldwide"])
                            job_location = job_location[0] if job_location and isinstance(job_location, list) else job_location or "Worldwide"

                            date_posted = job.get("date", "") or job.get("updated", "")
                            if not is_recent_job(date_posted):
                                continue

                            processed_job = {
                                "source": "CareerJet",
                                "title": job.get("title", "Job Title"),
                                "company": job.get("company", "Company"),
                                "location": job_location,
                                "salary": job.get("salary", ""),
                                "description": job.get("description", "")[:300] + "..." if job.get("description") else "",
                                "link": job.get("url", ""),
                                "date_posted": date_posted,
                            }
                            if processed_job["link"] and processed_job["link"].startswith('http'):
                                processed_jobs.append(processed_job)

                        print(f"CareerJet: Global search found {len(processed_jobs)} jobs")
                        set_cache_result(cache_key, processed_jobs)
                        return processed_jobs
        
        # For 403/429 errors, return empty gracefully
        elif response.status_code in (403, 429):
            if response.status_code == 403:
                print("[CareerJet] 403 - Access denied (IP/auth issue). Falling back to Jooble.")
            else:
                print("[CareerJet] 429 - Rate limited. Falling back to Jooble.")
            return []
        elif response.status_code == 401:
            print("[CareerJet] 401 Unauthorized - API key is invalid or expired")
            print(f"Response: {response.text[:200]}")
            print("ACTION: Update CAREERJET_API_KEY or CAREERJET_PUBLISHER_ID in your .env file\n")
            return []
        else:
            print(f"CareerJet: Error {response.status_code} - {response.text[:100]}")
            return []

    except requests.exceptions.Timeout:
        print("[CareerJet] Request timeout - server not responding")
        return []
    except requests.exceptions.ConnectionError as e:
        print(f"[CareerJet] Connection error: {str(e)[:100]}")
        return []
    except Exception as e:
        print(f"[CareerJet] Unexpected error: {str(e)[:100]}")
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
        ip = x_forwarded_for.split(',')[0].strip()
        if ip:
            return ip
    ip = request.META.get('HTTP_X_REAL_IP') or request.META.get('HTTP_CLIENT_IP')
    if ip:
        return ip.strip()
    return request.META.get('REMOTE_ADDR', '').strip()


AFRICA_PRIORITY_KEYWORDS = [
    'uganda', 'kampala', 'nairobi', 'accra', 'cairo', 'lagos', 'dar es salaam',
    'africa-remote', 'africa remote', 'remote africa', 'remote (africa)',
    'east africa', 'west africa', 'south africa', 'central africa'
]


def is_uganda_visitor(request):
    country_headers = [
        request.META.get('HTTP_CF_IPCOUNTRY', ''),
        request.META.get('HTTP_X_COUNTRY_CODE', ''),
        request.META.get('HTTP_GEOIP_COUNTRY_CODE', ''),
        request.META.get('HTTP_X_COUNTRY', ''),
    ]
    for header in country_headers:
        if header and header.strip().upper() in ('UG', 'UGA', 'UGANDA'):
            return True

    accept_language = request.META.get('HTTP_ACCEPT_LANGUAGE', '')
    if 'ug' in accept_language.lower().split(',')[0]:
        return True

    return False


def is_africa_priority_location(value):
    if not value:
        return False
    value = value.lower()
    return any(keyword in value for keyword in AFRICA_PRIORITY_KEYWORDS)


def is_external_africa_remote(job):
    location = (job.get('location') or '')
    return is_africa_priority_location(location)


def deduplicate_jobs(jobs_list):
    """
    Remove duplicate jobs based on title and company.
    Keeps the first occurrence of each unique job.
    """
    seen = set()
    unique_jobs = []
    
    for job in jobs_list:
        # Create a unique key from title and company (case-insensitive)
        key = (job.get('title', '').lower().strip(), job.get('company', '').lower().strip())
        
        if key not in seen and key != ('', ''):
            seen.add(key)
            unique_jobs.append(job)
    
    return unique_jobs


@allow_google_bot_or_login
def browse_job_listings(request):
    job_id = request.GET.get('job_id')
    selected_job = None
    
    if job_id:
        try:
            selected_job = JobPost.objects.get(pk=job_id)
        except (ValueError, JobPost.DoesNotExist):
            selected_job = None

    external_jobs = []
    priority_jobs = []

    category_filter = request.GET.get('category')
    search_query = request.GET.get('q') or ""
    location_query = request.GET.get('where', '').strip()
    # Allow any location, default to empty for global search
    effective_location = location_query if location_query else ""
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
            crawl_results = []
            try:
                from jobspy import scrape_jobs
                crawl_location = location_query or "Uganda"
                print(f"Starting jobspy crawl for '{search_query}' in '{crawl_location}'...")
                
                scraped_df = scrape_jobs(
                    site_name=["indeed", "linkedin", "zip_recruiter", "glassdoor", "monster", "careerbuilder"],
                    search_term=search_query,
                    location=crawl_location,
                    results_wanted=40,
                    hours_old=168,
                )
                
                for _, row in scraped_df.iterrows():
                    job_url = row.get('job_url') or row.get('url')
                    if not job_url:
                        continue
                    crawl_results.append({
                        'source': row.get('source', 'Web Search'),
                        'title': row.get('title', search_query),
                        'company': row.get('company', 'Global Employer'),
                        'location': row.get('location', crawl_location or 'Remote'),
                        'salary': row.get('salary', ''),
                        'description': row.get('description', '')[:320] + '...' if row.get('description') else 'Click to view full job details',
                        'link': job_url,
                        'date_posted': row.get('date_posted', ''),
                    })

                print(f"Crawl complete: found {len(crawl_results)} jobs")
                external_jobs = crawl_results

                if len(external_jobs) < 15:
                    print("Crawl results are low; adding API-sourced fallback jobs for better coverage.")
                    api_jobs = fetch_careerjet_data(request, search_query, effective_location) + fetch_jooble_data(search_query, effective_location)
                    external_jobs += api_jobs

                final_job_list = []
            except ImportError:
                messages.error(request, 'Deep search requires python-jobspy. Falling back to external API jobs. Install with: pip install python-jobspy')
                print("Jobspy not installed: falling back to API-based deep search")
                external_jobs = fetch_careerjet_data(request, search_query, effective_location) + fetch_jooble_data(search_query, effective_location)
                final_job_list = []
            except Exception as e:
                print(f"Crawl error: {e}")
                messages.error(request, f"Deep search failed: {str(e)}. Showing cached results instead.")
                external_jobs = fetch_careerjet_data(request, search_query, effective_location) + fetch_jooble_data(search_query, effective_location)
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

        uganda_visitor = is_uganda_visitor(request)
        priority_jobs = []
        if uganda_visitor and not effective_location:
            priority_candidates = [
                job for job in final_job_list
                if is_africa_priority_location(job.recruiter_location)
            ]
            priority_jobs = priority_candidates[:5]
            final_job_list = [job for job in final_job_list if job not in priority_jobs]

        # Fetch external jobs from both APIs for global coverage
        if search_type != 'crawl':
            # Fetch from both APIs to give user global options
            careerjet_jobs = fetch_careerjet_data(request, search_query or 'jobs', effective_location)
            jooble_jobs = fetch_jooble_data(search_query or 'jobs', effective_location)
            
            print(f"[Browse] Fetched {len(careerjet_jobs)} CareerJet, {len(jooble_jobs)} Jooble jobs")
            
            # Combine and deduplicate
            combined_jobs = careerjet_jobs + jooble_jobs
            external_jobs = deduplicate_jobs(combined_jobs)

            print(f"[Browse] After dedup: {len(external_jobs)} unique external jobs")

            if uganda_visitor and not effective_location:
                priority_external_jobs = [job for job in external_jobs if is_external_africa_remote(job)]
                external_jobs = priority_external_jobs + [job for job in external_jobs if job not in priority_external_jobs]

        paginator = Paginator(final_job_list, 20)
        posts_on_page = paginator.get_page(page)
        job_posts_context = posts_on_page
        context_priority_jobs = priority_jobs
    
    else:
        job_posts_context = []

    # Display location in page title (show "Worldwide" if empty)
    display_location = effective_location if effective_location else "Worldwide"
    
    context = {
        'selected_job': selected_job,
        'job_posts': job_posts_context,
        'priority_jobs': priority_jobs,
        'external_jobs': external_jobs,
        'solidgigs': solidgigs_data,
        'job_categories': JOB_CATEGORIES, 
        'selected_category': category_filter if category_filter in [c[0] for c in JOB_CATEGORIES] else 'all',
        'search_query': search_query,
        'location_query': effective_location,
        'search_type': search_type,
        'page_title': f"Africana AI Jobs in {display_location}",
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

import os
from pathlib import Path
from django.urls import reverse_lazy
import dj_database_url
import cloudinary
import cloudinary_storage
from dotenv import load_dotenv
import platform
import shutil

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'SECRET_KEY',
    'django-insecure-(p31q0!)f868y09ivx%&d&jjc&^jenjy6p2ozj%3pijiwm_2=f'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'
PREPEND_WWW = False  # Prevent CommonMiddleware from redirecting apex domain requests to www

# --- ALLOWED HOSTS ---
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# Custom canonical domain used for sitemap URLs and metadata
DEFAULT_DOMAIN = os.environ.get('DEFAULT_DOMAIN', 'www.africanaai.info')

# --- PRODUCTION SECURITY & CSRF FIXES ---
# Essential for apps behind proxies (Koyeb, Render, Heroku)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

if not DEBUG:
    # 1. Force Redirect to HTTPS
    SECURE_SSL_REDIRECT = True
    
    # 2. Strict Transport Security (HSTS) - Essential for the "Secure" padlock
    # 31536000 seconds = 1 year (production standard)
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # 3. Secure Cookies (Only sent over HTTPS)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True  # Prevents JavaScript from accessing cookies
    SESSION_COOKIE_SAMESITE = 'Strict'  # CSRF protection via SameSite cookies
    
    # 4. Modern Browser Protections
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'SAMEORIGIN'  # Prevent clickjacking (stricter than default)
    SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'
    # IMPORTANT: Careerjet tracking requires referrer to be sent to external domains
    SECURE_REFERRER_POLICY = "no-referrer-when-downgrade"
    
    # 5. Content Security Policy (CSP) - Critical defense against XSS
    # Restricts script sources to self and trusted CDNs
    SECURE_CSP_DEFAULT_SRC = ("'self'",)
    SECURE_CSP_SCRIPT_SRC = (
        "'self'",
        "https://unpkg.com",  # FFmpeg.wasm
        "https://cdn.jsdelivr.net",  # Optional: alternative CDN
        "https://trusted-domain.com",  # Replace with your trusted domains
    )
    SECURE_CSP_STYLE_SRC = (
        "'self'",
        "'unsafe-inline'",  # Required for Tailwind CSS
        "https://fonts.googleapis.com",
        "https://cdnjs.cloudflare.com",  # Bootstrap icons, etc.
    )
    SECURE_CSP_IMG_SRC = (
        "'self'",
        "data:",
        "https:",  # Allow all HTTPS images (Cloudinary, etc.)
    )
    SECURE_CSP_FONT_SRC = (
        "'self'",
        "https://fonts.gstatic.com",
        "https://cdnjs.cloudflare.com",
    )
    SECURE_CSP_CONNECT_SRC = (
        "'self'",
        "https://api.cloudinary.com",  # Cloudinary uploads
        "https://res.cloudinary.com",   # Cloudinary delivery
        "https://wa.me",  # WhatsApp integration
    )
    SECURE_CSP_MEDIA_SRC = (
        "'self'",
        "https:",  # Allow all HTTPS videos (local storage, Cloudinary)
    )
    SECURE_CSP_FRAME_SRC = (
        "'self'",
        "https://www.youtube.com",  # YouTube embeds
        "https://youtube.com",
    )
    SECURE_CSP_REPORT_URI = '/admin/csp-report/'  # Optional: CSP violation reporting

# --- CSRF TRUSTED ORIGINS ---
CSRF_TRUSTED_ORIGINS = [
    'https://uganda-languges-database.onrender.com',
    'https://www.africanaai.info',
    'https://africanaai.info',
]

if DEBUG:
    # Local development origins
    CSRF_TRUSTED_ORIGINS.extend([
        'http://127.0.0.1:8000',
        'http://localhost:8000',
    ])
else:
    # Dynamically add hosts from ALLOWED_HOSTS (HTTPS only for safety)
    for host in ALLOWED_HOSTS:
        clean_host = host.strip()
        if clean_host and clean_host != '*':
            if not clean_host.startswith(('http://', 'https://')):
                CSRF_TRUSTED_ORIGINS.append(f"https://{clean_host}")

# --- APPLICATION DEFINITION ---
INSTALLED_APPS = [
    'jazzmin',  # Must be before admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',
    'django.contrib.humanize',
    
    # Third-party
    'widget_tweaks',
    'cloudinary_storage',
    'cloudinary',
    'whitenoise.runserver_nostatic',
    'tailwind',
    'theme',

    # Local Apps
    'users',
    'eshop',
    'languages',
    'hotel',
    'movie',
    'social', 
]

TAILWIND_APP_NAME = 'theme'

# Dynamically find the npm path in the current environment
NPM_BIN_PATH = shutil.which("npm")

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'myuganda.middleware.CanonicalDomainMiddleware',  # Preserve canonical host while excluding crawler files
    'myuganda.middleware.WordPressProbeBlockMiddleware',  # Block wp-json, xmlrpc, wp-includes, and rest_route probes
    'myuganda.middleware.RateLimitMiddleware',  # Protect high-traffic endpoints and stop abuse bursts
    'whitenoise.middleware.WhiteNoiseMiddleware', # High-performance static serving
    'django.middleware.gzip.GZipMiddleware',  # Compress responses for faster loading
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'myuganda.middleware.HTTPMethodSecurityMiddleware',  # Restrict HTTP methods
    'myuganda.middleware.SecurityHeadersMiddleware',  # Add additional security headers
]

ROOT_URLCONF = 'myuganda.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'myuganda.wsgi.application'

# --- DATABASE ---
DATABASE_URL = os.environ.get("DATABASE_URL")
try:
    DB_CONN_MAX_AGE = int(os.environ.get("DB_CONN_MAX_AGE", "0"))
except (TypeError, ValueError):
    DB_CONN_MAX_AGE = 0

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=DB_CONN_MAX_AGE,
            ssl_require=True,
        )
    }
    DATABASES['default']['OPTIONS'] = {
        'keepalives': 1,
        'keepalives_idle': 30,
        'keepalives_interval': 10,
        'keepalives_count': 5,
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- AUTHENTICATION ---
AUTH_USER_MODEL = 'users.CustomUser'
LOGIN_URL = reverse_lazy('users:user_login')
LOGIN_REDIRECT_URL = reverse_lazy('hotel:social_feed')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- SESSION SETTINGS ---
SESSION_COOKIE_AGE = 31536000  # 1 year 
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# --- RATE LIMITING & TRAFFIC CONTROL ---
RATE_LIMIT_REQUESTS_PER_MINUTE = int(os.getenv('RATE_LIMIT_REQUESTS_PER_MINUTE', '120'))
RATE_LIMIT_BURST = int(os.getenv('RATE_LIMIT_BURST', '30'))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW_SECONDS', '60'))

# --- STATIC & MEDIA FILES ---
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# --- CLOUDINARY (FORCED HTTPS) ---
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
    'SECURE': True,  # Ensures all media URLs use https://
}

# --- API EXTERNAL CREDENTIALS ---
ADZUNA_APP_ID = os.getenv('ADZUNA_APP_ID')
ADZUNA_API_KEY = os.getenv('ADZUNA_API_KEY')
ALI_APP_KEY = os.getenv('ALI_APP_KEY')
ALI_APP_SECRET = os.getenv('ALI_APP_SECRET')
ALI_TRACKING_ID = os.getenv('ALI_TRACKING_ID')
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY")
TMDB_TOKEN = os.environ.get('TMDB_TOKEN')
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')

# Translation service endpoints
SUNBIRD_API_URL = os.getenv('SUNBIRD_API_URL', 'https://api.sunbird.ai')
SUNBIRD_API_KEY = os.getenv('SUNBIRD_API_KEY')
NLLB_API_URL = os.getenv('NLLB_API_URL', '')

# Cache backend selection. For production use with DatabaseCache, enable this explicitly
# and create the cache table via `python manage.py createcachetable`.
USE_DATABASE_CACHE = os.getenv('USE_DATABASE_CACHE', 'False').lower() in ('1', 'true', 'yes')
DJANGO_CACHE_TABLE = os.getenv('DJANGO_CACHE_TABLE', 'django_cache_table')
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1')
USE_REDIS_CACHE = os.getenv('USE_REDIS_CACHE', 'True').lower() in ('1', 'true', 'yes', 'on')

# --- STORAGE BACKENDS ---
# Check if Cloudinary is properly configured
CLOUDINARY_CONFIGURED = (
    os.environ.get('CLOUDINARY_CLOUD_NAME') and 
    os.environ.get('CLOUDINARY_API_KEY') and
    not os.environ.get('CLOUDINARY_API_KEY').startswith('your-')  # Placeholder check
)

if CLOUDINARY_CONFIGURED and not DEBUG:
    # Use Cloudinary in production when credentials are set
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "reels_video": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
else:
    # Use local file storage in development or when Cloudinary is not configured
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "reels_video": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get('FILE_UPLOAD_MAX_MEMORY_SIZE', str(10 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_UPLOAD_MAX_MEMORY_SIZE

# --- SITEMAP SETTINGS ---
SITEMAP_MAX_ITEMS = int(os.environ.get('SITEMAP_MAX_ITEMS', '1000'))

# --- JAZZMIN SETTINGS ---
JAZZMIN_SETTINGS = {
    "site_title": "Africana AI Admin",
    "site_header": "Africana AI",
    "site_brand": "Africana AI",
    "site_logo": "images/uganda_logo.png",
    "welcome_sign": "Africana AI Ecosystem Management",
    "copyright": "Africana AI Project",
    "search_model": ["users.CustomUser", "social.BusinessReel"], 
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "🛒 Sync AliExpress", "url": "/admin/eshop/product/sync-now/", "permissions": ["auth.view_user"]},
        {"name": "🎬 Sync Movies", "url": "/admin/movie/movie/sync-now/", "permissions": ["auth.view_user"]},
        {"name": "🏨 Sync Hotels", "url": "/admin/hotel/accommodation/sync/", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": ["auth", "users", "social", "languages", "eshop", "hotel"],
    "hide_apps": ["contenttypes", "sessions", "sites", "cloudinary_storage"],
    "hide_models": ["auth.Group"],
    "icons": {
        "auth": "fas fa-users-cog",
        "users.CustomUser": "fas fa-user-shield",
        "social.BusinessReel": "fas fa-video",
        "social.SecureMessage": "fas fa-envelope-shield",
        "social.SocialProfile": "fas fa-id-badge",
        "languages.Translation": "fas fa-language",
        "languages.JobPost": "fas fa-briefcase",
        "eshop.Product": "fas fa-shopping-cart",
        "hotel.Accommodation": "fas fa-hotel",
    },
}

JAZZMIN_UI_TWEAKS = {
    "theme": "flatly",
    "dark_mode_theme": "darkly",
    "navbar_fixed": True,
    "sidebar_fixed": True,
    "sidebar_nav_child_indent": True,
    "theme_cls": "darkly",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success"
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- LOGGING CONFIGURATION ---
# Disable mail_admins handler to prevent configuration errors in development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# --- CACHING CONFIGURATION ---
# Production-ready cache setup: prefer Redis, then DB cache, then local memory fallback.
if USE_REDIS_CACHE:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'uganda_db',
        }
    }
elif DATABASE_URL and not DEBUG and USE_DATABASE_CACHE:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': DJANGO_CACHE_TABLE,
        }
    }
elif not DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

# Use Redis for session storage when available so the app remains stateless across workers.
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
SESSION_CACHE_ALIAS = 'default'

# Celery configuration. This runs background tasks without blocking the request cycle.
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', REDIS_URL)
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'False').lower() in ('1', 'true', 'yes', 'on') and DEBUG

# If Redis is unavailable in a local dev environment, the app still starts without crashing.
if not USE_REDIS_CACHE and not DEBUG:
    CELERY_TASK_ALWAYS_EAGER = True


import os
from pathlib import Path
from django.urls import reverse_lazy
import dj_database_url # Import the dj_database_url library
# Cloudinary imports
import cloudinary
import cloudinary_storage

# NEW: Import the library to load environment variables from .env
from dotenv import load_dotenv


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# NEW: Load environment variables from the .env file
# This must be done before any os.environ.get() calls
load_dotenv(os.path.join(BASE_DIR, '.env'))


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-(p31q0!)f868y09ivx%&d&jjc&^jenjy6p2ozj%3pijiwm_2=f')

# SECURITY WARNING: don't run with debug turned on in production!
# Set DEBUG to False in production
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# Use environment variable for allowed hosts, falling back to a wildcard for flexibility.
# In Render, you would set the DJANGO_ALLOWED_HOSTS environment variable.
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# --- PRODUCTION FIXES FOR CSRF & PROXY SSL ---

# 1. Configure the Proxy Header
# Koyeb uses a reverse proxy. This setting tells Django to trust the 'X-Forwarded-Proto' 
# header, ensuring Django knows the connection is HTTPS, which is required for secure cookies 
# and CSRF to function correctly in production.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# 2. Configure trusted origins for CSRF protection
# The primary cause of CSRF failure in production is a missing or incorrect domain in trusted origins.

# The full hostname of your Koyeb deployment
KOYEB_HOST = 'initial-danette-africana-60541726.koyeb.app'

# List of all hosts to be trusted for CSRF
TRUSTED_HOSTS = [
    KOYEB_HOST,
]

# Add hosts from the ALLOWED_HOSTS environment variable
hosts_from_env = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
for host in hosts_from_env:
    # Add any allowed host that is not a wildcard
    if host.strip() and host.strip() != '*' and host.strip() not in TRUSTED_HOSTS:
        TRUSTED_HOSTS.append(host.strip())

# Construct CSRF_TRUSTED_ORIGINS by adding the HTTPS scheme to all trusted hosts.
# This is necessary because the browser sends the full origin.
CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in TRUSTED_HOSTS]

# Explicitly add local development origins (http)
CSRF_TRUSTED_ORIGINS.extend([
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1',
    'http://localhost',
])
# Note: Removed the redundant 'https://initial-danette-africana-60541726.koyeb.app/' 
# entry since it is already covered above and the trailing slash is incorrect.

# --- END PRODUCTION FIXES ---


# Application definition

INSTALLED_APPS = [
    # Jazzmin Admin Interface
    'users',
    'jazzmin',
    'django.contrib.admin',
    
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sites',  # required for sitemaps

    
    # NEW FIX: Add django.contrib.humanize for template tags like 'intcomma'
    'django.contrib.humanize', 

    # Third-party apps
    'widget_tweaks',
    'cloudinary_storage',
    'cloudinary',

    # My Apps (FIX: added 'languages' for Model lookup)
    'eshop',
    'languages', 
]

SITE_ID = 1


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

# Use dj_database_url to parse the DATABASE_URL environment variable
# for easy deployment setup (e.g., on Render or Heroku)
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
    }
else:
    # Fallback to SQLite for local development if DATABASE_URL is not set
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# --- Custom Authentication Configuration ---
AUTH_USER_MODEL = 'users.CustomUser' 

# Directs unauthenticated requests to your custom view
LOGIN_URL = reverse_lazy('users:user_login')

# The URL to redirect to after a user successfully logs in
LOGIN_REDIRECT_URL = reverse_lazy('languages:browse_job_listings')

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/ref/settings/#staticfiles

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
# When CLOUDINARY_STORAGE is enabled, files will be uploaded there
MEDIA_ROOT = os.path.join(BASE_DIR, 'media') 


# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Cloudinary Configuration
# Ensure these are set in your .env file or environment variables
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'


# Gemini API Key (for the AI Negotiation feature)
# Ensure this is set in your .env file or environment variables
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# # Jazzmin Admin (Uganda Language Database)
JAZZMIN_SETTINGS = {
    # --- Branding ---
    "site_title": "Uganda Language Admin",
    "site_header": "Uganda Languages",
    "site_brand": "Uganda Languages",
    "site_logo": "static/images/uganda_logo.png",
    "site_icon": "static/images/favicon.ico",
    "welcome_sign": "Welcome to the Uganda Language Database — preserving and managing local languages.",
    "user_avatar": None,

    # --- Search bar models ---
    "search_model": [
        "auth.User",
        "users.CustomUser",
        "languages.PhraseContribution",
        "languages.Translation",
        "languages.JobPost",
    ],

    # --- Top menu (balanced like LearnFlow) ---
    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "Support", "url": "https://github.com/farkasgabor/django-jazzmin/issues", "new_window": True},
        {"model": "auth.User"},
        {"model": "users.CustomUser"},
        {"model": "languages.PhraseContribution"},
        {"model": "languages.Translation"},
        {"model": "languages.JobPost"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,

    # --- User menu ---
    "usermenu_links": [
        {"name": "Profile", "url": "/profile/", "icon": "fas fa-user-circle"},
    ],

    # --- Sidebar ordering ---
    "order_with_respect_to": ["auth", "users", "languages"],

    # --- Hide redundant/system apps ---
    "hide_apps": ["contenttypes", "sessions", "sites", "cloudinary_storage", "cloudinary"],

    # --- Hide redundant models ---
    "hide_models": ["auth.Group"],

    # --- Icons ---
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "users.CustomUser": "fas fa-user-circle",
        "languages.PhraseContribution": "fas fa-language",
        "languages.Translation": "fas fa-book",
        "languages.JobPost": "fas fa-file-alt",
        "languages.Recruiter": "fas fa-address-card",
        "languages.JobCategory": "fas fa-sitemap",
        "languages.JobType": "fas fa-clock",
    },

    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    "related_modal_active": False,
}

# Jazzmin UI Tweaks (Uganda Language Database)
JAZZMIN_UI_TWEAKS = {
    # --- Theme & Colors ---
    "theme": "darkly",                  # modern dark theme
    "dark_mode_theme": "darkly",        # consistent dark mode
    "accent": "accent-primary",

    # Navbar & sidebar styling
    "navbar": "navbar-dark navbar-primary",
    "sidebar": "sidebar-dark-primary",

    # --- Layout ---
    "navbar_fixed": True,               # keep top bar visible
    "sidebar_fixed": True,              # keep sidebar visible
    "layout_boxed": True,               # center content (avoids “one side” look)
    "sidebar_nav_child_indent": True,   # indent child items for hierarchy
    "sidebar_nav_compact_style": False, # normal spacing
    "sidebar_nav_flat_style": False,    # keep hierarchy visible

    # --- Text sizes ---
    "navbar_small_text": False,
    "footer_small_text": False,
    "body_small_text": False,
    "sidebar_nav_small_text": False,
    "brand_small_text": False,

    # --- Buttons ---
    "button_classes": {
        "primary": "btn-outline-primary",
        "secondary": "btn-outline-secondary",
        "info": "btn-outline-info",
        "warning": "btn-outline-warning",
        "danger": "btn-outline-danger",
        "success": "btn-outline-success",
    },
    "actions_button_classes": {
        "add": "btn-success",
        "change": "btn-info",
        "delete": "btn-danger",
        "save": "btn-primary",
        "submit": "btn-primary",
    },

    # --- Other defaults ---
    "no_navbar_border": False,
    "footer_fixed": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_legacy_style": False,
}
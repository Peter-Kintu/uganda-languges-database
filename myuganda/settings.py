import os
from pathlib import Path
from django.urls import reverse_lazy
import dj_database_url
import cloudinary
import cloudinary_storage
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables
load_dotenv(os.path.join(BASE_DIR, '.env'))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-(p31q0!)f868y09ivx%&d&jjc&^jenjy6p2ozj%3pijiwm_2=f')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# --- PRODUCTION SECURITY & CSRF FIXES ---
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

KOYEB_HOST = 'initial-danette-africana-60541726.koyeb.app'
TRUSTED_HOSTS = [KOYEB_HOST]
env_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
for host in env_hosts:
    clean_host = host.strip()
    if clean_host and clean_host != '*' and clean_host not in TRUSTED_HOSTS:
        TRUSTED_HOSTS.append(clean_host)

CSRF_TRUSTED_ORIGINS = [f'https://{host}' for host in TRUSTED_HOSTS]
CSRF_TRUSTED_ORIGINS.extend(['http://127.0.0.1:8000', 'http://localhost:8000', 'http://127.0.0.1', 'http://localhost'])

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

    # Local Apps
    'users',
    'eshop',
    'languages', 
]

SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Crucial for Gunicorn/Render stability
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
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
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL, conn_max_age=600)
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
LOGIN_REDIRECT_URL = reverse_lazy('languages:browse_job_listings')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --- STATIC & MEDIA FILES ---
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
}

# Modern Storage Settings (Replaces DEFAULT_FILE_STORAGE)
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media') 

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# --- JAZZMIN SETTINGS (Better Design) ---
JAZZMIN_SETTINGS = {
    "site_title": "Uganda Language Admin",
    "site_header": "Uganda Languages",
    "site_brand": "Uganda Languages",
    "site_logo": "images/uganda_logo.png",
    "site_icon": "images/favicon.ico",
    "welcome_sign": "Database Management System",
    "copyright": "Uganda Language Project",
    "user_avatar": "avatar", 

    "search_model": ["users.CustomUser", "languages.PhraseContribution", "languages.JobPost"],

    "topmenu_links": [
        {"name": "Dashboard", "url": "admin:index", "permissions": ["auth.view_user"]},
        {"name": "View Site", "url": "/", "new_window": True},
        {"model": "users.CustomUser"},
    ],

    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": ["users", "languages", "eshop", "auth"],
    "hide_apps": ["contenttypes", "sessions", "sites", "cloudinary_storage"],
    "hide_models": ["auth.Group"],

    "icons": {
        "auth": "fas fa-users-cog",
        "users.CustomUser": "fas fa-user-shield",
        "languages.PhraseContribution": "fas fa-comments",
        "languages.Translation": "fas fa-language",
        "languages.JobPost": "fas fa-briefcase",
        "languages.Recruiter": "fas fa-id-card-alt",
        "eshop.Product": "fas fa-shopping-cart",
        "eshop.Order": "fas fa-file-invoice-dollar",
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
"""
Django settings for EventHub project.
"""
from decouple import config
from pathlib import Path
import os

try:
    import dj_database_url
except ImportError:
    dj_database_url = None

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file manually if exists
env_path = BASE_DIR / '.env'
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ.setdefault(key.strip(), val.strip())
# SECURITY: override with environment variable in production
SECRET_KEY = config('DJANGO_SECRET_KEY', default='django-insecure-j&#8z0n2)9txjmpi6=8i2h=d8ks8gt4gar#!kb0u0z6jd)im+#')
# Allow controlling debug via env var; default True for local development
DEBUG = config('DJANGO_DEBUG', default='True') == 'True'
ALLOWED_HOSTS = ['*']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'corsheaders',
    'django_extensions',
    
    # Local apps
    'accounts',
    'events',
    'bookings',
    'reviews',
    'payments',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'config.middleware.GlobalExceptionMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            os.path.join(BASE_DIR, 'frontend', 'templates'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'shared'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'shared', 'auth'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'shared', 'components'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'auth'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'dashboard'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'events'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'bookings'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'tickets'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'cart'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'wishlist'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'profile'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'support'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'notifications'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'payments'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'pages'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'errors'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'components'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'attendee', 'sections'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'auth'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'dashboard'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'events'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'tickets'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'bookings'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'attendees'),

            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'promotions'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'profile'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'settings'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'support'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'organizer', 'components'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'dashboard'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'events'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'bookings'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'users'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'tickets'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'payments'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'reports'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'settings'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'support'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'notifications'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'profile'),
            os.path.join(BASE_DIR, 'frontend', 'templates', 'admin', 'components'),
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.google_oauth',
            ],
        },
    },
]

# Only log to a file on writable filesystems (not Vercel/Render serverless)
_IS_SERVERLESS = bool(os.environ.get('VERCEL') or os.environ.get('RENDER'))

_log_handlers = {
    'console': {
        'class': 'logging.StreamHandler',
    },
}
_root_handlers = ['console']

if not _IS_SERVERLESS:
    _log_handlers['file'] = {
        'level': 'ERROR',
        'class': 'logging.FileHandler',
        'filename': os.path.join(BASE_DIR, 'events.log'),
    }
    _root_handlers.append('file')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': _log_handlers,
    'root': {
        'handlers': _root_handlers,
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': _root_handlers,
            'level': 'INFO',
            'propagate': False,
        },
        'config.middleware': {
            'handlers': _root_handlers,
            'level': 'ERROR',
            'propagate': False,
        },
    },
}


WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/tmp/db.sqlite3' if os.environ.get('VERCEL') else BASE_DIR / 'db.sqlite3',
    }
}

# If a DATABASE_URL environment variable is provided (Render/Postgres), use it.
if os.environ.get('DATABASE_URL'):
    DATABASES['default'] = dj_database_url.parse(
        os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )

# Caching Configuration - Shared Database Cache Backend
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache_table',
        'TIMEOUT': 300,  
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'frontend', 'static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'accounts.User'

# Login URLs
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

# Session Settings
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True
if os.environ.get('VERCEL') or not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# Email Settings
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.sendgrid.net')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'apikey')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'support@eventhub.com')

# CORS Settings
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# CSRF Settings
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:8000',
    'http://127.0.0.1:8000',
]
_site_url = (os.environ.get('SITE_URL') or '').strip().rstrip('/')
if _site_url:
    CSRF_TRUSTED_ORIGINS.append(_site_url)
_extra_csrf = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _extra_csrf:
    CSRF_TRUSTED_ORIGINS.extend(
        origin.strip().rstrip('/') for origin in _extra_csrf.split(',') if origin.strip()
    )
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# Google OAuth Config
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '229812600705-ih8rqfhe2jrv0lhb3vc4b7gt858p42fd.apps.googleusercontent.com')
SECURE_CROSS_ORIGIN_OPENER_POLICY = 'same-origin-allow-popups'
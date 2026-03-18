"""
File: settings.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: The Django settings for the project.
"""


from pathlib import Path
import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", get_random_secret_key())
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes", "on")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

raw_allowed = os.environ.get("ALLOWED_HOSTS", "")
allowed_hosts = {h.strip() for h in raw_allowed.split(",") if h.strip()}

# Keep local dev hosts available and auto-allow Fly app host in production.
default_hosts = {"localhost", "127.0.0.1", "[::1]"}
if not DEBUG:
    fly_app_name = os.environ.get("FLY_APP_NAME", "").strip()
    if fly_app_name:
        default_hosts.add(f"{fly_app_name}.fly.dev")
    default_hosts.add(".fly.dev")

ALLOWED_HOSTS = sorted(allowed_hosts | default_hosts)

CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    if host.startswith("."):
        CSRF_TRUSTED_ORIGINS.append(f"https://*{host}")
    elif host not in {"localhost", "127.0.0.1", "[::1]"}:
        CSRF_TRUSTED_ORIGINS.append(f"https://{host}")

INSTALLED_APPS = [
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'django_vite',
    "django_htmx",
    'accounts',
    'home',
    'ministry',
    'rzpercussion',
    'development_portfolio',
    'chatbot',
]

if DEBUG:
    INSTALLED_APPS.append("django_browser_reload")

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django_htmx.middleware.HtmxMiddleware",
]

if DEBUG:
    MIDDLEWARE.append("django_browser_reload.middleware.BrowserReloadMiddleware")

ROOT_URLCONF = 'conf.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ BASE_DIR / 'templates' ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'conf.wsgi.application'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME"),
        "USER": os.getenv("DB_USER"),
        "PASSWORD": os.getenv("DB_PWD"),
        "HOST": os.getenv("DB_HOST"),
        "PORT": os.getenv("DB_PORT"),
    }
}

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    result = urlparse(DATABASE_URL)
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": result.path.lstrip("/"),
        "USER": result.username,
        "PASSWORD": result.password,
        "HOST": result.hostname,
        "PORT": result.port,
    }


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / "static" / "dist", BASE_DIR / "static" / "public" ]
STATIC_ROOT = BASE_DIR / "staticfiles"

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "static" / "public"


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/account/login/"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG,
    }
}

UNFOLD = {
    "SITE_TITLE": "RZierke Admin",
    "SITE_HEADER": "RZierke Site",
    "SITE_SYMBOL": "dashboard",
}

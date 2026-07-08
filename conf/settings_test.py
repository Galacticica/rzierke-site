"""
File: settings_test.py
Description: Settings for the unit test suite. Overrides the DEBUG-coupled
security settings (which would 301 test requests to https), swaps the
database for in-memory SQLite, and keeps Vite in dev mode so templates
render without a built manifest.
"""

from conf.settings import *  # noqa: F401,F403

DEBUG = False

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]

# Whitenoise warns about the missing collectstatic output dir; tests serve
# static files through Django's own handlers instead.
MIDDLEWARE = [m for m in MIDDLEWARE if "whitenoise" not in m]  # noqa: F405

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# The OpenAI clients in chatbot.helpers are patched per-test; clearing the
# key keeps a forgotten mock from ever reaching the network.
OPENAI_API_KEY = None

DJANGO_VITE = {"default": {"dev_mode": True}}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "tests",
    }
}

LOGGING["root"]["level"] = "ERROR"  # noqa: F405

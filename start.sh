# Name:         django.sh
# Author:       Reagan Zierke <reagan.zierke@example.com>
# Created:      2025-09-04
# Description:  Setup a Django project using uv

#!/bin/bash
# setup_django_uv.sh
set -e

PROJECT_NAME=${1:-conf}

# Start uv
uv init
uv venv

# Install django
uv add django 
uv add django-browser-reload
uv add python-dotenv
uv run django-admin startproject conf

# Move manage.py to root
mv conf/manage.py ./

# Move inner conf/* to outer conf/
mv conf/conf/* conf/

# Remove old nested conf/
rmdir conf/conf

mkdir templates static media

uv run manage.py startapp accounts
cd accounts
mkdir templates
cd templates
mkdir accounts
cd ..
touch urls.py
touch forms.py
cd ..

# Configure settings.py
cat > conf/settings.py << 'EOF'
from pathlib import Path
import os
from dotenv import load_dotenv
from django.core.management.utils import get_random_secret_key

load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
# SECURITY WARNING: don't run with debug turned on in production!
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", get_random_secret_key())
DEBUG = os.environ.get("DEBUG", "0") == "1"

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    "django_browser_reload",
    'accounts',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

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

# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# DATABASES = {
#   'default': {
#       'ENGINE': 'django.db.backends.postgresql',
#       'NAME': os.getenv('DB_NAME'),
#       'USER': os.getenv('DB_USER'),
#       'PASSWORD': os.getenv('DB_PWD'),
#       'HOST': os.getenv('DB_HOST'),
#       'PORT': os.getenv('DB_PORT'),
#   }
# }

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'America/Chicago'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/
STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / "static" / "dist", BASE_DIR / "static" / "public" ]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / "static" / "public"

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
EOF

# Create environment variables
cat > .env << 'EOF'
# Django environment variables

# Use a fixed key in dev so sessions don't reset on every restart
SECRET_KEY=dev-secret-key-change-me

# Set to 1 for development, 0 for production
DEBUG=1

# Postgres Template
DB_HOST='pg-whatever.com'
DB_PORT='a number'
DB_USER='a user'
DB_NAME='a db name'
DB_PWD='a password'
EOF

# --- Patch urls.py ---
URLS_FILE="conf/urls.py"

sed -i "s/from django.urls import path/from django.urls import path, include/" $URLS_FILE

sed -i "/urlpatterns = \[/ a\ \ \ \ path('__reload__/', include('django_browser_reload.urls'))," $URLS_FILE
sed -i "/urlpatterns = \[/ a\ \ \ \ path('account/', include('accounts.urls'))," $URLS_FILE


# Creates a base.html template for Concordia colors
cat > templates/base.html << 'EOF'
{% load static %}

<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      :root {
        --concordia-blue: #192C53;
        --concordia-sky: #5A9DBF;
        --concordia-slate: #646464;
        --concordia-nimbus: #C8C8C8;
        --concordia-wheat: #E2C172;
        --concordia-white: #F8F4ED;
        --concordia-clay: #B2402A;
      }
    </style>
    <script src="https://unpkg.com/htmx.org@2.0.4" integrity="sha384-HGfztofotfshcF7+8n44JQL2oJmowVChPTg48S+jvZoztPfvwD79OC/LTtG6dMp+" crossorigin="anonymous"></script>
    <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/trix/1.3.1/trix.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>
    <style>
        trix-toolbar [data-trix-button-group="block-tools"] { 
            display: none;
        }
        
        trix-toolbar [data-trix-button-group="file-tools"] { 
            display: none;
        }
      </style>
    <title>Site Title</title>
</head>
<body class="min-h-screen flex flex-col bg-white">
    <header class="p-6" style="background-color: var(--concordia-blue); color: var(--concordia-white);">
        <div class="flex flex-col items-center font-sans">
            <h1>This is a header</h1>
        </div>
    </header>
    <main class="flex-grow">
        {% block content %}{% endblock %}
    </main>
    <footer class="text-white p-6 mt-4" style="background-color: var(--concordia-blue);">
        <div class="flex flex-col items-center font-sans">
            <p class="text-lg" style="color: var(--concordia-white);">© 2025</p>
        </div>
    </footer>
</body>
</html>
EOF

# Accounts creation

# Model
cat > accounts/models.py << 'EOF'
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifier."""
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and return a superuser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model with email as the unique identifier."""
    username = None  
    email = models.EmailField(unique=True)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return (self.first_name + " " + self.last_name).strip()
EOF

cat > accounts/admin.py << 'EOF'
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

admin.site.register(User)
EOF


# Forms
cat > accounts/forms.py << 'EOF'
from django import forms
from django.contrib.auth import authenticate as auth_authenticate


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        required=True, 
        widget=forms.TextInput(attrs={"placeholder": "Email Address", "class": "form-control"}),
        label="Email"
    )
    password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"}),
        label="Password"
    )

    def __init__(self, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
    
    def clean(self):
        self.user_cache = auth_authenticate(
           self.request,
           username=self.cleaned_data.get("email"),
              password=self.cleaned_data.get("password")
        )
        if self.user_cache is None:
           raise forms.ValidationError("Invalid email or password.")
        return super().clean()
    def get_user(self):
        return self.user_cache
    

class SignupForm(forms.Form):

    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Email Address", "class": "form-control"}),
        label="Email"
    )
    password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Password", "class": "form-control"}),
        label="Password"
    )
    confirm_password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm Password", "class": "form-control"}),
        label="Confirm Password"
    )
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "First Name", "class": "form-control"}),
        label="First Name"
    )
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={"placeholder": "Last Name", "class": "form-control"}),
        label="Last Name"
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

EOF


# Views
cat > accounts/views.py << 'EOF'
from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from django.views.generic.edit import FormView
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.views import View
from .forms import LoginForm, SignupForm


User = get_user_model()

class MyLoginView(LoginView):
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

class MySignupView(FormView):
    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = "/" 

    def form_valid(self, form):
        user = User.objects.create(
            email=form.cleaned_data["email"],
            username=form.cleaned_data["email"],
            first_name=form.cleaned_data["first_name"],
            last_name=form.cleaned_data["last_name"],
            password=make_password(form.cleaned_data["password"]), 
        )
        login(self.request, user)
        return super().form_valid(form)

    def form_invalid(self, form):
        return super().form_invalid(form)

class MyLogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)  
        return redirect("/")  

EOF


# URLS
cat > accounts/urls.py << 'EOF'
from django.urls import path
from .views import MyLoginView, MySignupView, MyLogoutView


urlpatterns = [
    path("login/", MyLoginView.as_view(), name="login_page"),
    path("signup/", MySignupView.as_view(), name="signup_page"),
    path("logout/", MyLogoutView.as_view(), name="logout_page"),
]
EOF


# Templates
cat > accounts/templates/accounts/login.html << 'EOF'
{% extends "base.html" %}
{% load static %}

{% block content %}
<div>
    <div>
        <h2>Log In</h2>
        <form method="post" action="{% url 'login_page' %}">
            {% csrf_token %}
            {{ form.non_field_errors }}
            <div>
                <label for="id_email">Email</label>
                {{ form.email }}
                {{ form.email.errors }}
            </div>
            <div>
                <label for="id_password">Password</label>
                {{ form.password }}
                {{ form.password.errors }}
            </div>
            <button type="submit">Log In</button>
        </form>
        <div>
            <p>No Account Yet? <a href="{% url 'signup_page' %}">Sign Up</a></p>
        </div>
    </div>
</div>
{% endblock %}
EOF

cat > accounts/templates/accounts/signup.html << 'EOF'
{% extends "base.html" %}
{% load static %}

{% block content %}
<div>
    <div>
        <h2>Sign Up</h2>
        <form method="post" action="{% url 'signup_page' %}">
            {% csrf_token %}
            {{ form.non_field_errors }}
            <div>
                {{ form.first_name.label_tag }}
                {{ form.first_name }}
                {{ form.first_name.errors }}
            </div>
            <div>
                {{ form.last_name.label_tag }}
                {{ form.last_name }}
                {{ form.last_name.errors }}
            </div>
            <div>
                {{ form.email.label_tag }}
                {{ form.email }}
                {{ form.email.errors }}
            </div>
            <div>
                {{ form.password.label_tag }}
                {{ form.password }}
                {{ form.password.errors }}
            </div>
            <div>
                {{ form.confirm_password.label_tag }}
                {{ form.confirm_password }}
                {{ form.confirm_password.errors }}
            </div>
            <div>
                {{ form.role.label_tag }}
                {{ form.role }}
                {{ form.role.errors }}
            </div>
            <button type="submit">Sign Up</button>
        </form>
        <div>
            <p>Already have an account? 
                <a href="{% url 'login_page' %}">Log In</a>
            </p>
        </div>
    </div>
</div>
{% endblock %}
EOF


# Finalize by activating venv and running migrations
source .venv/bin/activate

uv run python manage.py makemigrations accounts
uv run python manage.py migrate

uv run python manage.py runserver

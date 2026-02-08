"""
File: views.py
Author: Reagan Zierke <reaganzierke@gmail.com>
Date: 2026-02-05
Description: Views for user authentication and registration.
"""


from django.shortcuts import redirect
from django.contrib.auth.views import LoginView
from django.views.generic.edit import FormView
from django.contrib.auth import login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.views import View
from django.http import HttpResponse
from .forms import LoginForm, SignupForm
from .models import AccessRequest


User = get_user_model()

class MyLoginView(LoginView):
    """The login view for user authentication."""
    form_class = LoginForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

class MySignupView(FormView):
    """The signup view for new user registration."""
    form_class = SignupForm
    template_name = "accounts/signup.html"
    success_url = "/" 

    def get_context_data(self, **kwargs):
        """Add 'next' parameter to template context."""
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get('next', '')
        return context

    def get_success_url(self):
        """Redirect to 'next' parameter if present, otherwise to home."""
        next_url = self.request.GET.get('next') or self.request.POST.get('next')
        return next_url if next_url else self.success_url

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
    """The logout view for user sign out."""
    def get(self, request, *args, **kwargs):
        logout(request)
        next_url = request.GET.get('next')
        if not next_url:
            next_url = request.META.get('HTTP_REFERER', '/')
        return redirect(next_url)


class RequestAccessView(View):
    """View to handle access requests for private content."""
    
    def post(self, request, *args, **kwargs):
        request_type = request.POST.get('request_type', 'performance')
        
        if request.user.is_authenticated:
            email = request.user.email
        else:
            email = request.POST.get('email', 'anonymous')
        
        # Create the access request
        AccessRequest.objects.create(
            email=email,
            request_type=request_type
        )
        
        # Return success message for HTMX
        return HttpResponse("""
            <div class="text-center px-6">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mx-auto mb-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p class="text-lg font-semibold mb-2">Request Submitted</p>
                <p class="text-base-content/70 text-sm">Your access request has been logged and will be reviewed.</p>
            </div>
        """)  


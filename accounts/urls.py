from django.urls import path
from .views import MyLoginView, MySignupView, MyLogoutView


urlpatterns = [
    path("login/", MyLoginView.as_view(), name="login_page"),
    path("signup/", MySignupView.as_view(), name="signup_page"),
    path("logout/", MyLogoutView.as_view(), name="logout_page"),
]

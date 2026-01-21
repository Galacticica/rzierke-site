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


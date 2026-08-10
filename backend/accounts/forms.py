from django import forms
from django.contrib.auth.forms import AuthenticationForm

class CustomLoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email'})
    )
    
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'})
    )

    login_type = forms.CharField(widget=forms.HiddenInput(), initial='ADMIN')
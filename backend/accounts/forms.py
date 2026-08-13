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

    def confirm_login_allowed(self, user):
        if not user.is_active:
            if user.is_locked_out:
                raise forms.ValidationError(
                    'Your account has been locked out due to 5 failed login attempts. '
                    'Please contact an administrator to unlock it.',
                    code='locked_out',
                )
            raise forms.ValidationError(
                    'Your account has been deactivated. '
                    'Please contact an administrator.',
                    code='inactive',
            )
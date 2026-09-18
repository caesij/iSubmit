from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model

User = get_user_model()

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
        if user.is_locked_out:
            raise forms.ValidationError(
                'Your account has been locked out due to 5 failed login attempts. '
                'Please contact an administrator to unlock it.',
                code='locked_out',
            )
            
        if not user.is_active:
            raise forms.ValidationError(
                    'Your account has been deactivated. '
                    'Please contact an administrator.',
                    code='inactive',
            )
            
class FacultyProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'middle_name', 'last_name', 'email', 'profile_photo']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        query = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise forms.ValidationError('A user with this email address already exists.')
        return email

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'size'):
            if photo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Image must be smaller than 10MB.')
        return photo

class AdminStaffProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'middle_name', 'last_name', 'email', 'profile_photo']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        query = User.objects.filter(email__iexact=email)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise forms.ValidationError('A user with this email address already exists.')
        return email

    def clean_profile_photo(self):
        photo = self.cleaned_data.get('profile_photo')
        if photo and hasattr(photo, 'size'):
            if photo.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Image must be smaller than 10MB.')
        return photo
    
class PreferencesForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['language', 'timezone', 'date_format', 'time_format']
        widgets = {
            'timezone': forms.Select(choices=[
                ('Asia/Manila', '(GMT +08:00) Manila, Philippines'),
                ('UTC', '(GMT +00:00) UTC'),
            ]),
        }
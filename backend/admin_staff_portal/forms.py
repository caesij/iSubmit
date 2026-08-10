from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from accounts.models import User

class UserManagementForm(forms.ModelForm):

    class Meta:
        model = User
        fields = ['email', 'first_name', 'middle_name', 'last_name', 'faculty_type', 'is_active']

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        self.assigned_role = kwargs.pop('initial_role', None) or User.Role.FACULTY
        super().__init__(*args, **kwargs)

        target_role = self.instance.role if self.instance.pk else self.assigned_role
        if target_role != User.Role.FACULTY:
            self.fields['faculty_type'].widget = forms.HiddenInput()
            self.fields['faculty_type'].required = False

    # Validate Email
    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        
        try:
            validate_email(email)
        except ValidationError:
            raise ValidationError("Please enter a valid email address.")

        query = User.objects.filter(email__iexact=email)
        
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)
            
        if query.exists():
            raise ValidationError("An account with this email address already exists.")

        return email

    # Data Cleaning
    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name', '').strip()
        return first_name.upper() if first_name else ''

    def clean_middle_name(self):
        middle_name = self.cleaned_data.get('middle_name', '').strip()
        return middle_name.upper() if middle_name else ''

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name', '').strip()
        return last_name.upper() if last_name else ''

    def clean(self):
        cleaned_data = super().clean()
        faculty_type = cleaned_data.get('faculty_type')
        target_role = self.instance.role if self.instance.pk else self.assigned_role

        if target_role == User.Role.FACULTY and not faculty_type:
            self.add_error('faculty_type', 'Faculty type is required for faculty accounts.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)

        if not user.pk:
            user.role = self.assigned_role

        if user.role != User.Role.FACULTY:
            user.faculty_type = None

        if commit:
            user.save()
        return user
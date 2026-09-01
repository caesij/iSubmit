from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from accounts.models import User

class BaseUserManagementForm(forms.ModelForm):
    
    is_active = forms.TypedChoiceField(
        choices=[(True, 'Active'), (False, 'Inactive')],
        coerce=lambda x: x == 'True',
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Account Status',
    )
    
    class Meta:
        model = User
        fields = [
            'first_name',
            'middle_name',
            'last_name',
            'employee_ID',
            'email',
            'is_active',
        ]

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

        field_placeholders = {
            'first_name': 'Enter first name',
            'middle_name': 'Enter middle name',
            'last_name': 'Enter last name',
            'employee_ID': 'Enter employee ID',
            'email': 'Enter institutional email',
        }

        for field_name, placeholder in field_placeholders.items():
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-input',
                    'placeholder': placeholder,
                })

        if 'is_active' in self.fields:
            self.fields['is_active'].widget.attrs.update({
                'class': 'form-select',
            })

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

    # Employee ID Cleaning
    def clean_employee_ID(self):
        employee_id = self.cleaned_data.get('employee_ID', '').strip()

        if not employee_id:
            raise ValidationError("Employee ID is required.")

        query = User.objects.filter(employee_ID__iexact=employee_id)
        if self.instance.pk:
            query = query.exclude(pk=self.instance.pk)

        if query.exists():
            raise ValidationError("A user with this employee ID already exists.")

        return employee_id

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
            raise ValidationError("A user with this email address already exists.")

        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        if user._state.adding:
            user.role = self.assigned_role
        if commit:
            user.save()
        return user

class StaffManagementForm(BaseUserManagementForm):
    assigned_role = User.Role.STAFF

class FacultyManagementForm(BaseUserManagementForm):
    assigned_role = User.Role.FACULTY

    class Meta(BaseUserManagementForm.Meta):
        fields = BaseUserManagementForm.Meta.fields + ['faculty_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'faculty_type' in self.fields:
            self.fields['faculty_type'].widget.attrs.update({
                'class': 'form-select',
            })

    def clean_faculty_type(self):
        faculty_type = self.cleaned_data.get('faculty_type')
        if not faculty_type:
            raise ValidationError('Faculty type is required for faculty accounts.')
        return faculty_type
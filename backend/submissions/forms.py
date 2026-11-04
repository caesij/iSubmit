import os
import datetime
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from submissions.models import Requirement, DraftUpload, DocumentReview

User = get_user_model()

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

def _academic_year_choices():
    current_year = datetime.date.today().year
    return [
        (f'{y}-{y + 1}', f'{y}-{y + 1}')
        for y in range(current_year - 1, current_year + 6)
    ]

class RequirementForm(forms.ModelForm):
    academic_year = forms.ChoiceField(choices=_academic_year_choices, label="Academic Year")

    class Meta:
        model = Requirement
        fields = [
            'requirement_title',
            'category',
            'assigned_faculty_type',
            'assigned_programs',
            'assigned_faculty_member',
            'academic_year',
            'semester',
            'status',
            'deadline',
            'text_extraction_enabled',
            'validation_enabled',
            'validation_instructions'
        ]

        widgets = {
            'deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
            'text_extraction_enabled': forms.CheckboxInput,
        }

        error_messages = {
            'unique_together': 'A requirement with this title already exists for the selected academic year and semester.'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['validation_enabled'].label = 'Enable NLP validation'
        self.fields['text_extraction_enabled'].label = 'Enable text extraction'
        self.fields['validation_instructions'].label = 'Required validation fields'
        self.fields['validation_instructions'].help_text = ('One per line using only: Field name: required')
        self.fields['deadline'].input_formats = ['%Y-%m-%dT%H:%M']
        self.fields['requirement_title'].label = 'Requirement Title'
        faculty_field = self.fields['assigned_faculty_member']
        faculty_field.queryset = User.objects.filter(role=User.Role.FACULTY, is_active=True).order_by('last_name', 'first_name')
        faculty_field.label_from_instance = lambda user: user.get_full_name()
        self.fields['category'].widget.attrs['placeholder'] = 'Category'
        self.fields['requirement_title'].widget.attrs['placeholder'] = 'Requirement Title'

        if self.instance and self.instance.pk and self.instance.academic_year:
            parsed = self._parse_academic_year(self.instance.academic_year)
            if parsed:
                start_year, end_year = parsed
                self.fields['academic_year'].initial = f'{start_year}-{end_year}'

    @staticmethod
    def _parse_academic_year(value):
        try:
            years_part = value.replace('A.Y.', '').strip()
            start_str, end_str = years_part.split('-')
            return int(start_str.strip()), int(end_str.strip())
        except (ValueError, AttributeError):
            return None

    def clean_requirement_title(self):
        title = self.cleaned_data.get('requirement_title', '').strip()

        if not title:
            raise ValidationError('Please enter a requirement title.')
        return title

    def clean_category(self):
        category = self.cleaned_data.get('category', '').strip()

        if not category:
            raise ValidationError('Please enter a category.')
        return category

    def clean_validation_instructions(self):
        from core.document_validation import parse_validation_instructions

        instructions = self.cleaned_data.get('validation_instructions', '').strip()
        fields, errors = parse_validation_instructions(instructions)
        if errors:
            raise ValidationError(errors)
        if self.cleaned_data.get('validation_enabled') and not fields:
            raise ValidationError(
                'Add at least one required field when NLP validation is enabled.'
            )
        return instructions

    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year', '')
        try:
            start_str, end_str = academic_year.split('-')
            start_year, end_year = int(start_str), int(end_str)
        except (ValueError, AttributeError):
            raise ValidationError('Please select a valid academic year.')

        if end_year != start_year + 1:
            raise ValidationError('Please select an academic year with consecutive years.')

        return academic_year

    def clean(self):
        cleaned_data = super().clean()
        selected_faculty = cleaned_data.get('assigned_faculty_member')

        if selected_faculty:
            cleaned_data['assigned_faculty_type'] = None
            cleaned_data['assigned_programs'] = self.fields['assigned_programs'].queryset.none()

        title = cleaned_data.get('requirement_title')
        academic_year = cleaned_data.get('academic_year')
        semester = cleaned_data.get('semester')

        if title and academic_year and semester:
            normalized_academic_year = f'A.Y. {academic_year}'

            duplicates = Requirement.objects.filter(
                requirement_title=title,
                academic_year=normalized_academic_year,
                semester=semester
            )

            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)

            if duplicates.exists():
                self.add_error(
                    None,
                    'A requirement with this title already exists for the selected academic year and semester.'
                )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.academic_year = f'A.Y. {self.cleaned_data["academic_year"]}'
        if commit:
            instance.save()
            self.save_m2m()
        return instance

class DraftUploadForm(forms.ModelForm):
    class Meta:
        model = DraftUpload
        fields = ['draft_file']

    def clean_draft_file(self):
        file = self.cleaned_data['draft_file']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                'This file type is not supported. Please upload a PDF, DOCX, or XLSX file.'
            )
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError('Please choose a file smaller than 10 MB.')
        return file

class DocumentRevisionForm(forms.Form):
    file = forms.FileField()

    def clean_file(self):
        file = self.cleaned_data['file']
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                'This file type is not supported. Please upload a PDF, DOCX, or XLSX file.'
            )

        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError('Please choose a file smaller than 10 MB.')

        return file

class DocumentReviewForm(forms.ModelForm):
    class Meta:
        model = DocumentReview
        fields = ['remarks']

    def __init__(self, *args, **kwargs):
        self.reviewer = kwargs.pop('reviewer', None)
        self.revision = kwargs.pop('revision', None)
        super().__init__(*args, **kwargs)

    def clean_remarks(self):
        remarks = self.cleaned_data.get('remarks', '').strip()

        return remarks

    def save(self, commit=True):
        review = super().save(commit=False)

        if not self.reviewer:
            raise ValueError("DocumentReviewForm.save() requires a 'reviewer'.")
        if not self.revision:
            raise ValueError("DocumentReviewForm.save() requires a 'revision'.")

        review.reviewed_by = self.reviewer
        review.revision = self.revision

        if commit:
            review.save()

        return review

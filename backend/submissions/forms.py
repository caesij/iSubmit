import os
from django import forms
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from collections import Counter

from submissions.models import SubmissionPeriod, DraftUpload, DocumentReview

User = get_user_model()

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

from collections import Counter

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseFormSet, formset_factory
from django.utils import timezone

from submissions.models import Requirement, SubmissionPeriod

LOCKED_FIELDS = ('unit', 'applies_to', 'text_extraction_enabled', 'validation_enabled', 'validation_instructions')


def current_academic_start_year():
    today = timezone.localdate()
    return today.year if today.month >= 6 else today.year - 1


def academic_year_choices():
    start = current_academic_start_year()
    return [(f'{year}-{year + 1}', f'{year}-{year + 1}') for year in range(start - 1, start + 4)]


class PeriodForm(forms.ModelForm):
    academic_year = forms.ChoiceField(choices=academic_year_choices, label='Academic Year')

    class Meta:
        model = SubmissionPeriod
        fields = ['academic_year', 'semester', 'deadline']
        widgets = {
            'deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M'
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deadline'].input_formats = ['%Y-%m-%dT%H:%M']

        if self.instance.pk:
            del self.fields['academic_year'], self.fields['semester']
        else:
            start = current_academic_start_year()
            self.fields['academic_year'].initial = f'{start}-{start + 1}'

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if not self.instance.pk and deadline <= timezone.now():
            raise ValidationError('The deadline must be in the future.')
        return deadline

class RequirementRowForm(forms.Form):
    use_required_attribute = False

    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    include = forms.BooleanField(required=False, initial=True)
    
    requirement_title = forms.CharField(
        max_length=255,
        label='Requirement Title',
        widget=forms.TextInput(attrs={'placeholder': 'Requirement title'}),
    )
    
    is_required = forms.BooleanField(required=False, initial=True, label='Required')
    
    unit = forms.ChoiceField(
        choices=Requirement.Unit.choices,
        initial=Requirement.Unit.PER_YEAR_LEVEL,
        label='Uploads owed',
    )
    
    applies_to = forms.ChoiceField(
        choices=Requirement.AppliesTo.choices,
        initial=Requirement.AppliesTo.ALL,
        label='Applies to',
    )
    
    text_extraction_enabled = forms.BooleanField(required=False, label='Enable text extraction')
    validation_enabled = forms.BooleanField(required=False, label='Enable NLP validation')
    validation_instructions = forms.CharField(
        required=False,
        label='Required validation fields',
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Examples only — enter your own fields:\nCourse code: required\nCourse title: required\nSection: required\nAcademic year: required',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True

        self.locked = bool(self.initial.get('locked'))
        if self.locked:
            for name in LOCKED_FIELDS:
                self.fields[name].disabled = True

    def has_changed(self):
        return bool(self['include'].data or self['id'].data)

    def clean_requirement_title(self):
        return ' '.join(self.cleaned_data['requirement_title'].split())

    def clean(self):
        from core.document_validation import parse_validation_instructions

        cleaned = super().clean()
        instructions = cleaned.get('validation_instructions', '').strip()
        cleaned['validation_instructions'] = instructions

        if cleaned.get('validation_enabled') and not cleaned.get('text_extraction_enabled'):
            self.add_error('validation_enabled', 'NLP validation needs text extraction to be enabled.')

        fields, errors = parse_validation_instructions(instructions)
        if errors:
            self.add_error('validation_instructions', errors)
        elif cleaned.get('validation_enabled') and not fields:
            self.add_error(
                'validation_instructions',
                'Add at least one required field when NLP validation is enabled.'
            )

        return cleaned


class BaseRequirementFormSet(BaseFormSet):
    def clean(self):
        if any(self.errors):
            return

        rows = [form.cleaned_data for form in self.forms if form.cleaned_data]

        if not any(row['include'] for row in rows):
            raise ValidationError('Select at least one requirement.')

        title_counts = Counter(row['requirement_title'].lower() for row in rows)
        duplicates = [title for title, count in title_counts.items() if count > 1]
        if duplicates:
            raise ValidationError('Requirement titles must be unique. Duplicated: ' + ', '.join(duplicates))


RequirementFormSet = formset_factory(RequirementRowForm, formset=BaseRequirementFormSet, extra=0)

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

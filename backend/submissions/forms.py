import os
import datetime
from django import forms
from submissions.models import Requirement, DraftUpload, DocumentRevision, DocumentReview
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xlsx'}
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
            'assigned_to', 
            'academic_year',
            'status', 
            'deadline'
        ]
        
        widgets = {
            'deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
        }
       
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['deadline'].input_formats = ['%Y-%m-%dT%H:%M']
    
        if self.instance and self.instance.pk and self.instance.academic_term:
            parsed = self._parse_academic_term(self.instance.academic_term)
            if parsed:
                start_year, end_year = parsed
                self.fields['academic_year'].initial = f'{start_year}-{end_year}'

    @staticmethod
    def _parse_academic_term(value):
        try:
            years_part = value.replace('A.Y.', '').strip()
            start_str, end_str = years_part.split('-')
            return int(start_str.strip()), int(end_str.strip())
        except (ValueError, AttributeError):
            return None

    def clean_requirement_title(self):
        title = self.cleaned_data.get('requirement_title', '').strip()
        
        if not title:
            raise ValidationError('Requirement title is required.')
        return title
    
    def clean_category(self):
        category = self.cleaned_data.get('category', '').strip()
        if not category:
            raise ValidationError('Category is required.')
        return category
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year', '')
        try:
            start_str, end_str = academic_year.split('-')
            start_year, end_year = int(start_str), int(end_str)
        except (ValueError, AttributeError):
            raise ValidationError('Invalid academic year selected.')

        if end_year != start_year + 1:
            raise ValidationError('Invalid academic year range.')

        return academic_year

    def clean(self):
        cleaned_data = super().clean()
        academic_year = cleaned_data.get('academic_year')

        if academic_year:
            cleaned_data['academic_term'] = f'A.Y. {academic_year}'

        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.academic_term = self.cleaned_data['academic_term']
        if commit:
            instance.save()
        return instance
    
class DraftUploadForm(forms.ModelForm):
    class Meta:
        model = DraftUpload
        fields = ['draft_file']

    def clean_draft_file(self):
        file = self.cleaned_data['draft_file']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file type: {ext}")
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError("File too large. Maximum size is 10MB.")
        return file
    
class DocumentRevisionForm(forms.ModelForm):
    class Meta:
        model = DocumentRevision
        fields = ['file']

    def __init__(self, *args, **kwargs):
        self.submission = kwargs.pop('submission', None)
        super().__init__(*args, **kwargs)

    def clean_file(self):
        file = self.cleaned_data['file']
        ext = os.path.splitext(file.name)[1].lower()
        
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file type: {ext}")
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError("File too large. Maximum size is 10MB.")
        
        return file

    def save(self, commit=True, submission=None):
        revision = super().save(commit=False)

        submission = submission or self.submission
        
        if not submission:
            raise ValueError("DocumentRevisionForm.save() requires a 'submission', either via the 'submission' argument or at init.")
            
        revision.submission = submission

        last_version = (
            submission.revisions.order_by('-version_number')
            .values_list('version_number', flat=True)
            .first()
        )
        
        revision.version_number = (last_version or 0) + 1

        if commit:
            revision.save()

        return revision

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

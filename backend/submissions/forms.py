import os
from django import forms
from submissions.models import Requirement, DocumentSubmission, DocumentRevision, DocumentReview
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {'.pdf', '.doc', '.docx', '.xlsx'}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

class BaseSubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = [
            'requirement_title', 
            'category', 
            'assigned_to', 
            'academic_term', 
            'completion_progress', 
            'status', 
            'deadline'
        ]
        
    def clean_requirement_title(self):
        title = self.cleaned_data.get('requirement_title', '').strip()
        
        if not title:
            raise ValidationError("Requirement title is required.")
        return title

class DocumentSubmissionForm(BaseSubmissionForm):
    
    class Meta:
        model = DocumentSubmission
        fields = ['document_title']
        
    document_file = forms.FileField(
        widget=forms.ClearableFileInput(
            attrs={'accept': '.pdf,.doc,.docx,.xlsx'}
        ),
    )

    def clean_document_file(self):
        file = self.cleaned_data['document_file']
        ext = os.path.splitext(file.name)[1].lower()
        
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(f"Unsupported file type: {ext}")
        if file.size > MAX_UPLOAD_SIZE:
            raise ValidationError("File too large. Maximum size is 10MB.")
        
        return file
    

    def save(self, commit=True, faculty=None):
        faculty = faculty or self.request_user
        
        if not faculty:
            raise ValueError(
                "DocumentSubmissionForm.save() requires a faculty user, either via the 'faculty' argument or 'request_user' at init."
            )
        
        submission = super().save(commit=False)
        submission.faculty = faculty

        if commit:
            submission.save()
            
            last_version = (
                submission.revisions.order_by('-version_number')
                .values_list('version_number', flat=True)
                .first()
            )
            
            next_version = (last_version or 0) + 1

            DocumentRevision.objects.create(
                submission=submission,
                file=self.cleaned_data['document_file'],
                version_number=next_version,
            )

        return submission
    
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
        
        if not remarks:
            raise ValidationError("Remarks are required.")
        
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

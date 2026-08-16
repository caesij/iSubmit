import os
from django import forms
from submissions.models import DocumentRevision, DocumentSubmission, Requirement
from django.core.exceptions import ValidationError

class BaseSubmissionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)

class RequirementForm(forms.ModelForm):
    class Meta:
        model = Requirement
        fields = ['requirement_title', 'category', 'deadline']
        
    def clean_requirement_name(self):
        name = self.cleaned_data.get('requirement_name', '').strip()
        if not name:
            raise ValidationError("Requirement name is required.")
        return name
    
    def clean_document_file(self):
        file = self.cleaned_data['document_file']
        ext = os.path.splitext(file.name)[1].lower()
        if ext not in {'.pdf', '.doc', '.docx'}:
            raise ValidationError(f"Unsupported file type: {ext}")
        if file.size > 10 * 1024 * 1024:
            raise ValidationError("File too large. Maximum size is 10MB.")
        return file

class DocumentSubmissionForm(forms.ModelForm):
    document_file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'accept': '.pdf,.doc,.docx'})
    )

    class Meta:
        model = DocumentSubmission
        fields = ['document_title']

    def save(self, commit=True, faculty=None):
        submission = super().save(commit=False)
        if faculty:
            submission.faculty = faculty
        if commit:
            submission.save()
            DocumentRevision.objects.create(
                submission=submission,
                file=self.cleaned_data['document_file'],
                version_number=1,
            )
        return submission
from django.db import models
from django.db.models import Q
import uuid
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector

def draft_upload_path(instance, filename):
    return f'drafts/user_{instance.faculty.id}/{filename}'

def submission_upload_path(instance, filename):
    return f'submissions/user_{instance.faculty.id}/{filename}'


class Requirement(models.Model):
    class ReqStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
    
    class AssignedFacultyType(models.TextChoices):
        ALL = 'ALL', 'All Faculty'
        FULL_TIME = 'FULL_TIME', 'Full-Time Faculty'
        PART_TIME = 'PART_TIME', 'Part-Time Faculty'
        
    class Semester(models.TextChoices):
        FIRST_SEM = 'FIRST_SEM', '1st Semester'
        SECOND_SEM = 'SECOND_SEM', '2nd Semester'
        SUMMER = 'SUMMER', 'Summer'

    requirement_title = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    
    academic_term = models.CharField(max_length=255)
    
    semester = models.CharField(
        max_length=10,
        choices=Semester.choices,
        default=Semester.FIRST_SEM
    )
    
    deadline = models.DateTimeField()
    class TextProcessingMode(models.TextChoices):
        NONE = 'NONE', 'No text processing'
        DIGITAL = 'DIGITAL', 'Extract digital text'
        OCR = 'OCR', 'Extract text with OCR'

    text_processing_mode = models.CharField(
        max_length=10,
        choices=TextProcessingMode.choices,
        default=TextProcessingMode.NONE
    )
    nlp_enabled = models.BooleanField(default=False)
    
    assigned_to = models.CharField(
        max_length=20,
        choices=AssignedFacultyType.choices,
        default=AssignedFacultyType.ALL
    )
    
    status = models.CharField(
        max_length=20,
        choices=ReqStatus.choices,
        default=ReqStatus.ACTIVE
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['requirement_title', 'academic_term', 'semester'],
                name='unique_requirement_per_term_semester'
            )
        ]
        
        indexes = [
            GinIndex(
                fields=['requirement_title'],
                opclasses=['gin_trgm_ops'],
                name='req_title_trgm'
            )
        ]

    @property
    def completion_progress(self):
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()

        faculty_qs = UserModel.objects.filter(role=UserModel.Role.FACULTY)
        if self.assigned_to != self.AssignedFacultyType.ALL:
            faculty_qs = faculty_qs.filter(faculty_type=self.assigned_to)

        total_faculty = faculty_qs.count()
        if total_faculty == 0:
            return 0

        submitted_count = self.submissions.filter(
            faculty_id__in=faculty_qs.values_list('id', flat=True)
        ).values('faculty_id').distinct().count()

        return round((submitted_count / total_faculty) * 100)
    
    def __str__(self):
        return self.requirement_title
    
    
class DraftUpload(models.Model):
    class DraftStatus(models.TextChoices):
        NO_FILE = 'NO_FILE', 'No File Yet'
        ATTACHED = 'ATTACHED', 'Attached'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='draft_uploads'
    )

    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='draft_uploads'
    )

    draft_file = models.FileField(upload_to=draft_upload_path, blank=True)

    draft_created_at = models.DateTimeField(auto_now_add=True)
    draft_updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['faculty', 'requirement'],
                name='unique_faculty_requirement_draft'
            )
        ]

    @property
    def status(self):
        return self.DraftStatus.ATTACHED if self.draft_file else self.DraftStatus.NO_FILE

    def __str__(self):
        return f'Draft: {self.requirement.requirement_title} by {self.faculty.username}'


class DocumentSubmission(models.Model):
    class SubmissionStatus(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Reviewed - Pending Approval'
        NEEDS_REVISION = 'NEEDS_REVISION', 'Needs Revision'
        RESUBMITTED = 'RESUBMITTED', 'Resubmitted'
        APPROVED = 'APPROVED', 'Approved'

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    
    status = models.CharField(
        max_length=30,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED
    )
    
    document_file = models.FileField(upload_to=submission_upload_path)
    
    is_pinned = models.BooleanField(default=False)

    initially_submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    revisioned_at = models.DateTimeField(null=True, blank=True)
    resubmitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_submissions'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_submissions'
    )

    def __str__(self):
        return f'Submission: {self.requirement.requirement_title} by {self.faculty.username}'


class DocumentRevision(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    submission = models.ForeignKey(
        DocumentSubmission,
        on_delete=models.CASCADE,
        related_name='revisions'
    )

    version_number = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['submission', 'version_number'],
                name='unique_submission_version'
            )
        ]

        ordering = ['-version_number']

    def __str__(self):
        return (
            f'{self.submission.requirement.requirement_title} '
            f'- Revision {self.version_number}'
        )


class DocumentReview(models.Model):
    revision = models.ForeignKey(
        DocumentRevision,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_remarks'
    )

    remarks = models.TextField(null=True, blank=True)

    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        reviewer = self.reviewed_by.username if self.reviewed_by else 'Unknown'
        return f'Review for {self.revision.submission.requirement.requirement_title} - Revision {self.revision.version_number} by {reviewer}'


class DocumentMetadata(models.Model):
    class OCRStatus(models.TextChoices):
        NOT_REQUIRED = 'NOT_REQUIRED', 'Not Required'
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class NLPStatus(models.TextChoices):
        NOT_REQUIRED = 'NOT_REQUIRED', 'Not Required'
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        PASSED = 'PASSED', 'Passed'
        FAILED = 'FAILED', 'Failed'

    id = models.AutoField(primary_key=True)

    faculty = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_metadata_records'
    )
    requirement = models.ForeignKey(
        Requirement,
        on_delete=models.CASCADE,
        related_name='document_metadata_records'
    )

    draft = models.OneToOneField(
        DraftUpload,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='document_metadata'
    )
    
    submission = models.ForeignKey(
        DocumentSubmission,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='metadata_versions'
    )
    version_number = models.PositiveIntegerField(default=1)

    original_filename = models.CharField(max_length=512, blank=True)
    storage_file_name = models.CharField(max_length=2048, blank=True)
    content_type = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)

    ocr_status = models.CharField(
        max_length=20,
        choices=OCRStatus.choices,
        default=OCRStatus.NOT_REQUIRED,
        db_index=True
    )
    extracted_text = models.TextField(blank=True)
    ocr_error = models.TextField(blank=True)
    ocr_request_id = models.PositiveIntegerField(
        default=1,
        editable=False,
        db_index=True
    )
    ocr_completed_at = models.DateTimeField(null=True, blank=True)

    nlp_status = models.CharField(
        max_length=20,
        choices=NLPStatus.choices,
        default=NLPStatus.NOT_REQUIRED,
        db_index=True
    )
    
    nlp_result = models.JSONField(default=dict, blank=True)
    nlp_error = models.TextField(blank=True)
    nlp_completed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(draft__isnull=False, submission__isnull=True)
                    | Q(draft__isnull=True, submission__isnull=False)
                ),
                name='document_metadata_has_draft_or_submission'
            ),
            models.UniqueConstraint(
                fields=['submission', 'version_number'],
                condition=Q(submission__isnull=False),
                name='unique_document_metadata_submission_version'
            )
        ]
        
        indexes = [
            GinIndex(
                SearchVector('extracted_text', config='english'),
                name='dm_extracted_fts_gin'
            ),
            GinIndex(
                fields=['extracted_text'],
                opclasses=['gin_trgm_ops'],
                name='dm_extracted_trgm'
            )
        ]

    @property
    def is_ready_for_submission(self):
        text_extraction_ready = (
            self.requirement.text_processing_mode == Requirement.TextProcessingMode.NONE
            or self.ocr_status == self.OCRStatus.COMPLETED
        )
        nlp_ready = (
            not self.requirement.nlp_enabled
            or self.nlp_status == self.NLPStatus.PASSED
        )
        return text_extraction_ready and nlp_ready

    def __str__(self):
        return f'Metadata for {self.original_filename or self.requirement.requirement_title}'
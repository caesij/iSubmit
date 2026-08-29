from django.db import models
import uuid
from django.conf import settings

def draft_upload_path(instance, filename):
    return f'drafts/user_{instance.faculty.id}/{filename}'

def submission_upload_path(instance, filename):
    return f'submissions/user_{instance.faculty.id}/{filename}'

def revision_upload_path(instance, filename):
    return f'submissions/user_{instance.submission.faculty.id}/{filename}'

class Requirement(models.Model):
    class ReqStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'
    
    class AssignedFacultyType(models.TextChoices):
        ALL = 'ALL', 'All Faculty'
        FULL_TIME = 'FULL_TIME', 'Full-Time Faculty'
        PART_TIME = 'PART_TIME', 'Part-Time Faculty'
        
    class Semester(models.TextChoices):
        FIRST = 'FIRST', 'First Semester'
        SECOND = 'SECOND', 'Second Semester'
        SUMMER = 'SUMMER', 'Summer'

    requirement_title = models.CharField(max_length=255)
    category = models.CharField(max_length=255)
    
    academic_term = models.CharField(max_length=255)
    
    semester = models.CharField(
        max_length=10,
        choices=Semester.choices,
        default=Semester.FIRST
    )
    
    deadline = models.DateTimeField()
    
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

    file = models.FileField(upload_to=revision_upload_path)

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
        return f'{self.submission.requirement.requirement_title} - Revision {self.version_number}'

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
from django.db import models
import uuid
from django.conf import settings

def user_directory_path(instance, filename):
    return f'submissions/user_{instance.faculty.id}/{filename}'

class Requirement(models.Model):
    requirement_name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deadline = models.DateTimeField()

    def __str__(self):
        return self.name


class DocumentSubmission(models.Model):

    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        UNDER_REVIEW = 'UNDER_REVIEW', 'Under Review'
        NEEDS_REVISION = 'NEEDS_REVISION', 'Needs Revision'
        RESUBMITTED = 'RESUBMITTED', 'Resubmitted'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

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

    document_title = models.CharField(max_length=255)
    requirements = models.ManyToManyField(Requirement, related_name='submissions')

    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.SUBMITTED
    )

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
        return self.title


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

    file = models.FileField(
        upload_to=user_directory_path,
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
            f'{self.submission.title} - Revision {self.version_number}'
        )


class DocumentReview(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    revision = models.ForeignKey(
        DocumentRevision,
        on_delete=models.CASCADE,
        related_name='reviews'
    )

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='document_reviews'
    )

    comments = models.TextField()

    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f'Review for {self.revision.submission.title} - Revision {self.revision.version_number} by {self.reviewed_by.username}'
        )
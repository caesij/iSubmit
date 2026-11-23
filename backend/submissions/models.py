import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector
from django.core.validators import RegexValidator
from django.db import models, transaction
from django.db.models import Count, Q
from django.db.models.functions import Lower
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.exceptions import ValidationError


def draft_upload_path(instance, filename):
    return f'drafts/user_{instance.faculty.id}/{filename}'

def submission_upload_path(instance, filename):
    return f'submissions/user_{instance.faculty.id}/{filename}'


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

class StatusModel(models.Model):
    class ReqStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        INACTIVE = 'INACTIVE', 'Inactive'

    status = models.CharField(
        max_length=20,
        choices=ReqStatus.choices,
        default=ReqStatus.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    @property
    def is_active(self):
        return self.status == self.ReqStatus.ACTIVE

    def toggle_status(self):
        self.status = self.ReqStatus.INACTIVE if self.is_active else self.ReqStatus.ACTIVE
        self.save(update_fields=['status', 'updated_at'])


def active_q(prefix=''):
    active = StatusModel.ReqStatus.ACTIVE
    return Q(**{f'{prefix}status': active, f'{prefix}period__status': active})


def required_q(prefix=''):
    return Q(**{f'{prefix}is_required': True})


class RequirementBase(models.Model):
    class Unit(models.TextChoices):
        PER_SECTION = 'PER_SECTION', 'One per section'
        PER_YEAR_LEVEL = 'PER_YEAR_LEVEL', 'One per course and year level'
        PER_FACULTY = 'PER_FACULTY', 'One per faculty'

    class AppliesTo(models.TextChoices):
        ALL = 'ALL', 'All courses'
        REGULAR = 'REGULAR', 'Regular courses (not OJT)'
        OJT = 'OJT', 'OJT courses only'
        LAB = 'LAB', 'Courses with a laboratory'

    # The fields a staff member can edit on the checklist
    SETTING_FIELDS = (
        'requirement_title',
        'unit',
        'applies_to',
        'is_required',
        'text_extraction_enabled',
        'validation_enabled',
        'validation_instructions',
    )

    requirement_title = models.CharField(max_length=255)
    order = models.PositiveSmallIntegerField(default=0)

    unit = models.CharField(max_length=20, choices=Unit.choices, default=Unit.PER_YEAR_LEVEL)
    applies_to = models.CharField(max_length=10, choices=AppliesTo.choices, default=AppliesTo.ALL)

    is_required = models.BooleanField(default=True)

    text_extraction_enabled = models.BooleanField(default=False)
    validation_enabled = models.BooleanField(default=False)
    validation_instructions = models.TextField(blank=True)

    class Meta:
        abstract = True

    def applies_to_course(self, course):
        if self.applies_to == self.AppliesTo.REGULAR:
            return not course.is_ojt
        if self.applies_to == self.AppliesTo.OJT:
            return course.is_ojt
        if self.applies_to == self.AppliesTo.LAB:
            return course.has_lab
        return True

    def __str__(self):
        return self.requirement_title


# ---------------------------------------------------------------------------
# Period -> Requirements
# ---------------------------------------------------------------------------

class SubmissionPeriodQuerySet(models.QuerySet):
    def with_progress(self):
        owed = Q(requirements__status=StatusModel.ReqStatus.ACTIVE) & required_q('requirements__')
        needs_revision = DocumentSubmission.SubmissionStatus.NEEDS_REVISION

        return self.annotate(
            requirement_count=Count(
                'requirements',
                filter=Q(requirements__status=StatusModel.ReqStatus.ACTIVE),
                distinct=True,
            ),
            total_slots=Count('requirements__slots', filter=owed),
            submitted_slots=Count(
                'requirements__slots__submission',
                filter=owed & ~Q(requirements__slots__submission__status=needs_revision),
            ),
        )


class SubmissionPeriod(StatusModel):
    class Semester(models.TextChoices):
        FIRST_SEM = 'FIRST_SEM', '1st Semester'
        SECOND_SEM = 'SECOND_SEM', '2nd Semester'
        SUMMER = 'SUMMER', 'Summer'

    academic_year = models.CharField(max_length=9)
    semester = models.CharField(
        max_length=10,
        choices=Semester.choices,
        default=Semester.FIRST_SEM
    )
    deadline = models.DateTimeField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_submission_periods'
    )

    objects = SubmissionPeriodQuerySet.as_manager()

    class Meta:
        ordering = ['-deadline']
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'semester'],
                name='unique_period_per_academic_year_semester',
                violation_error_message='A period for this academic year and semester already exists.'
            )
        ]

    @property
    def academic_year_display(self):
        return f'A.Y. {self.academic_year}'

    @property
    def completion_progress(self):
        if not self.pk:
            return 0

        if not hasattr(self, 'total_slots'):
            return type(self).objects.with_progress().get(pk=self.pk).completion_progress

        return round(self.submitted_slots / self.total_slots * 100) if self.total_slots else 0

    def __str__(self):
        return f'{self.academic_year_display} - {self.get_semester_display()}'


class RequirementQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active_q())

    def with_progress(self):
        needs_revision = DocumentSubmission.SubmissionStatus.NEEDS_REVISION

        return self.annotate(
            total_slots=Count('slots'),
            submitted_slots=Count('slots__submission', filter=~Q(slots__submission__status=needs_revision)),
        )


class Requirement(StatusModel, RequirementBase):
    period = models.ForeignKey(
        SubmissionPeriod,
        on_delete=models.PROTECT,
        related_name='requirements'
    )

    objects = RequirementQuerySet.as_manager()

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(
                Lower('requirement_title'),
                'period',
                name='unique_requirement_title_per_period'
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
    def deadline(self):
        return self.period.deadline

    @property
    def is_overdue(self):
        return self.period.deadline < timezone.now()

    @property
    def completion_progress(self):
        if not self.pk:
            return 0

        if not hasattr(self, 'total_slots'):
            return type(self).objects.with_progress().get(pk=self.pk).completion_progress

        if not self.total_slots:
            return 0

        return round(self.submitted_slots / self.total_slots * 100)


class RequirementTemplate(RequirementBase):
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order', 'id']
        constraints = [
            models.UniqueConstraint(Lower('requirement_title'), name='unique_requirement_template_title')
        ]


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=150)
    is_ojt = models.BooleanField(
        default=False,
        help_text='OJT / practicum course. It gets the OJT requirements instead of the regular exam and teaching-material ones.'
    )
    has_lab = models.BooleanField(default=False, help_text='Needs a Laboratory Manual.')

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.title}'


class ClassAssignment(models.Model):
    academic_year = models.CharField(
        max_length=9,
        validators=[RegexValidator(r'^\d{4}-\d{4}$', 'Use the format 2026-2027.')]
    )
    semester = models.CharField(max_length=10, choices=SubmissionPeriod.Semester.choices)

    faculty = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='class_assignments')
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='class_assignments')
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='class_assignments')

    year_level = models.PositiveSmallIntegerField()
    section = models.CharField(max_length=10, help_text='The part after the year level. For section 1-4 enter 4.')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'semester', 'faculty', 'course', 'program', 'year_level', 'section'],
                name='unique_class_assignment'
            )
        ]
    
    def clean(self):
        super().clean()

        if not self.program_id:
            return

        errors = {}

        program = self.program

        # Validate year level against program duration
        if (self.year_level is not None and self.year_level > program.duration_years):
            errors['year_level'] = ('The selected year level exceeds the program duration.')

        # Validate section number before converting it
        section = (self.section or '').strip()

        if not section.isascii() or not section.isdecimal() or int(section) < 1:
            errors['section'] = 'Enter a valid section number.'

        else:
            section_number = int(section)
            self.section = str(section_number)

            section_exists = self.program.sections.filter(
                academic_year=self.academic_year,
                year_level=self.year_level,
                section=section_number,
            ).exists()

            if not section_exists:
                errors['section'] = (
                    'This section does not exist for the selected program, academic year, and year level.'
                )

        # Validate whether the course belongs to the selected program
        if self.course_id and not program.courses.filter(
            pk=self.course_id,
        ).exists():
            errors['course'] = ('This course is not included in the selected program.')

        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.faculty} - {self.course.code} - {self.program.short_name} {self.year_level}-{self.section}'


class UploadSlotQuerySet(models.QuerySet):
    def active(self):
        return self.filter(active_q('requirement__'))

    def required(self):
        return self.filter(required_q('requirement__'))

    def progress_by_faculty(self):
        needs_revision = DocumentSubmission.SubmissionStatus.NEEDS_REVISION
        return (
            self.active().required()
            .values('faculty')
            .annotate(
                total=Count('pk'),
                completed=Count('submission', filter=~Q(submission__status=needs_revision)),
            )
        )


class UploadSlot(models.Model):
    faculty = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='upload_slots')
    requirement = models.ForeignKey(Requirement, on_delete=models.CASCADE, related_name='slots')

    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    program = models.ForeignKey('programs.Program', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    year_level = models.PositiveSmallIntegerField(null=True, blank=True)
    section = models.CharField(max_length=10, blank=True)

    key = models.CharField(max_length=60)

    objects = UploadSlotQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['faculty', 'requirement', 'key'], name='unique_upload_slot')
        ]

    @staticmethod
    def make_key(course_id, program_id, year_level, section):
        return ':'.join('' if part is None else str(part) for part in (course_id, program_id, year_level, section))

    def title_with(self, requirement_title):
        return f'{requirement_title} ({self.label})' if self.course_id else requirement_title

    @property
    def full_title(self):
        return self.title_with(self.requirement.requirement_title)

    @property
    def label(self):
        if not self.course_id:
            return 'Whole faculty'

        if self.section:
            group = f'{self.year_level}-{self.section}'
        elif self.year_level:
            group = f'Year {self.year_level}'
        else:
            group = ''

        program = self.program.short_name if self.program_id else ''
        return f"{self.course.code} - {' '.join(filter(None, (program, group)))}".strip(' -')


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

    slot = models.OneToOneField(
        UploadSlot,
        on_delete=models.CASCADE,
        related_name='draft'
    )

    draft_file = models.FileField(upload_to=draft_upload_path, blank=True)

    draft_created_at = models.DateTimeField(auto_now_add=True)
    draft_updated_at = models.DateTimeField(auto_now=True)

    @property
    def status(self):
        return self.DraftStatus.ATTACHED if self.draft_file else self.DraftStatus.NO_FILE

    def __str__(self):
        return f'Draft: {self.requirement.requirement_title} by {self.faculty.get_full_name()}'


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

    slot = models.OneToOneField(
        UploadSlot,
        on_delete=models.CASCADE,
        related_name='submission'
    )

    status = models.CharField(
        max_length=30,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED
    )

    document_file = models.FileField(upload_to=submission_upload_path)

    initially_submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_remarks = models.TextField(blank=True)
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

    is_pinned = models.BooleanField(default=False)

    is_archived = models.BooleanField(default=False, db_index=True)

    archived_at = models.DateTimeField(null=True, blank=True)

    archive_expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True
    )

    @property
    def full_title(self):
        return self.slot.title_with(self.requirement.requirement_title)

    def __str__(self):
        return f'Submission: {self.requirement.requirement_title} by {self.faculty.get_full_name()}'


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
        reviewer = self.reviewed_by.get_full_name() if self.reviewed_by else 'Unknown'
        return f'Review for {self.revision.submission.requirement.requirement_title} - Revision {self.revision.version_number} by {reviewer}'


class DocumentMetadata(models.Model):
    class TextExtractionStatus(models.TextChoices):
        NOT_REQUIRED = 'NOT_REQUIRED', 'Not Required'
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    class ValidationStatus(models.TextChoices):
        NOT_REQUIRED = 'NOT_REQUIRED', 'Not Required'
        PENDING = 'PENDING', 'Pending'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
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

    text_extraction_status = models.CharField(
        max_length=20,
        choices=TextExtractionStatus.choices,
        default=TextExtractionStatus.NOT_REQUIRED,
        db_index=True
    )

    extracted_text = models.TextField(blank=True)
    text_extraction_error = models.TextField(blank=True)

    text_extraction_request_id = models.PositiveIntegerField(
        default=1,
        editable=False,
        db_index=True
    )

    text_extraction_completed_at = models.DateTimeField(null=True, blank=True)

    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.NOT_REQUIRED,
        db_index=True,
    )
    validation_result = models.JSONField(default=dict, blank=True)
    validation_error = models.TextField(blank=True)
    validation_completed_at = models.DateTimeField(null=True, blank=True)

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
            not self.requirement.text_extraction_enabled
            or self.text_extraction_status == self.TextExtractionStatus.COMPLETED
        )

        return text_extraction_ready

    def __str__(self):
        return f'Metadata for {self.original_filename or self.requirement.requirement_title}'


@receiver([post_save, post_delete], sender=ClassAssignment)
def resync_upload_slots(sender, instance, **kwargs):
    from submissions.slots import sync_upload_slots

    periods = SubmissionPeriod.objects.filter(academic_year=instance.academic_year, semester=instance.semester)
    for period in periods:
        transaction.on_commit(lambda period=period: sync_upload_slots(period))


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def resync_upload_slots_for_new_user(sender, instance, created, **kwargs):
    if not created:
        return

    from submissions.slots import sync_upload_slots

    for period in SubmissionPeriod.objects.filter(status=StatusModel.ReqStatus.ACTIVE):
        transaction.on_commit(lambda period=period: sync_upload_slots(period))

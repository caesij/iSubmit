from django.contrib import admin
from django.contrib.auth import get_user_model

from submissions.models import (
    Requirement,
    DraftUpload,
    DocumentSubmission,
    DocumentRevision,
    DocumentReview,
    DocumentMetadata
)

User = get_user_model()

# Requirement Management for Superuser
@admin.register(Requirement)
class RequirementAdmin(admin.ModelAdmin):
    list_display = (
        'requirement_title',
        'category',
        'academic_year',
        'semester',
        'deadline',
        'assigned_faculty_type',
        'status',
        'text_extraction_enabled',
        'validation_enabled',
    )

    list_filter = (
        'status',
        'semester',
        'academic_year',
        'assigned_faculty_type',
        'text_extraction_enabled',
        'validation_enabled',
    )

    search_fields = (
        'requirement_title',
        'category',
        'academic_year',
    )

    filter_horizontal = (
        'assigned_programs',
        'assigned_faculty_member',
    )

    readonly_fields = (
        'created_at',
        'updated_at',
    )

    date_hierarchy = 'deadline'

    ordering = ('-created_at',)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == 'assigned_faculty_member':
            kwargs['queryset'] = User.objects.filter(
                role=User.Role.FACULTY,
                is_active=True,
            ).order_by('last_name', 'first_name')

        return super().formfield_for_manytomany(
            db_field,
            request,
            **kwargs,
        )


# Workflow Records: Read-only
class ReadOnlyModelAdmin(admin.ModelAdmin):
    def get_readonly_fields(self, request, obj=None):
        return tuple(
            field.name
            for field in self.model._meta.fields
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# Draft Upload Management for Superuser
@admin.register(DraftUpload)
class DraftUploadAdmin(ReadOnlyModelAdmin):
    list_display = (
        'faculty',
        'requirement',
        'status',
        'draft_created_at',
        'draft_updated_at',
    )

    list_filter = (
        'draft_created_at',
        'draft_updated_at',
    )

    search_fields = (
        'faculty__email',
        'faculty__employee_ID',
        'faculty__first_name',
        'faculty__last_name',
        'requirement__requirement_title',
    )

    date_hierarchy = 'draft_created_at'


# Document Submission Management for Superuser
@admin.register(DocumentSubmission)
class DocumentSubmissionAdmin(ReadOnlyModelAdmin):
    list_display = (
        'requirement',
        'faculty',
        'status',
        'initially_submitted_at',
        'reviewed_at',
        'approved_at',
        'is_pinned',
        'is_archived',
    )

    list_filter = (
        'status',
        'is_pinned',
        'is_archived',
        'initially_submitted_at',
    )

    search_fields = (
        'faculty__email',
        'faculty__employee_ID',
        'faculty__first_name',
        'faculty__middle_name',
        'faculty__last_name',
        'requirement__requirement_title',
    )

    date_hierarchy = 'initially_submitted_at'

    ordering = ('-initially_submitted_at',)


# Document Revision Management for Superuser
@admin.register(DocumentRevision)
class DocumentRevisionAdmin(ReadOnlyModelAdmin):
    list_display = (
        'submission',
        'version_number',
        'uploaded_at',
    )

    search_fields = (
        'submission__faculty__email',
        'submission__faculty__employee_ID',
        'submission__requirement__requirement_title',
    )

    date_hierarchy = 'uploaded_at'

    ordering = ('-uploaded_at',)


# Document Review Management for Superuser
@admin.register(DocumentReview)
class DocumentReviewAdmin(ReadOnlyModelAdmin):
    list_display = (
        'revision',
        'reviewed_by',
        'reviewed_at',
    )

    search_fields = (
        'reviewed_by__email',
        'revision__submission__faculty__email',
        'revision__submission__requirement__requirement_title',
    )

    date_hierarchy = 'reviewed_at'

    ordering = ('-reviewed_at',)


# Document Metadata Management for Superuser
@admin.register(DocumentMetadata)
class DocumentMetadataAdmin(ReadOnlyModelAdmin):
    list_display = (
        'original_filename',
        'faculty',
        'requirement',
        'version_number',
        'text_extraction_status',
        'validation_status',
        'created_at',
    )

    list_filter = (
        'text_extraction_status',
        'validation_status',
        'content_type',
        'created_at',
    )

    search_fields = (
        'original_filename',
        'storage_file_name',
        'faculty__email',
        'faculty__employee_ID',
        'requirement__requirement_title',
    )

    date_hierarchy = 'created_at'

    ordering = ('-created_at',)
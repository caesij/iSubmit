from admin_staff_portal.views.core.dashboard_views import (
    admin_dashboard_data_view,
    admin_dashboard_view,
    
    staff_dashboard_data_view,
    staff_dashboard_view,
)

from admin_staff_portal.views.core.document_repo_views import (
    document_repo_view,
    document_archive_view,
    archive_document_view,
    restore_document_view,
    permanently_delete_document_view,
    bulk_archive_document_view,
    bulk_restore_document_view,
    bulk_permanently_delete_document_view,
    document_file_view,
)

from admin_staff_portal.views.core.requirement_management_views import (
    requirements_list,
    period_editor,
    period_detail,
    toggle_period_status,
    toggle_requirement_status,
    edit_requirement,
)

from admin_staff_portal.views.core.faculty_submission_views import (
    faculty_submissions_list,
    faculty_submission_bins_view,
    review_submission,
    mark_under_review_view,
    mark_needs_revision_view,
    mark_reviewed_view,
    approve_selected_submissions_view,
)

from admin_staff_portal.views.general.settings_views import (
    preferences_view,
    notification_settings_view,
    account_and_security_view,
    staff_permissions_view,
)

from admin_staff_portal.views.general.profile_views import profile_view

__all__ = [
    'admin_dashboard_data_view',
    'admin_dashboard_view',
    
    'staff_dashboard_data_view',
    'staff_dashboard_view',
    
    'document_repo_view',
    'document_archive_view',
    'archive_document_view',
    'restore_document_view',
    'permanently_delete_document_view',
    'bulk_archive_document_view',
    'bulk_restore_document_view',
    'bulk_permanently_delete_document_view',
    'document_file_view',

    'requirements_list',
    'period_editor',
    'period_detail',
    'toggle_period_status',
    'toggle_requirement_status',
    'edit_requirement',
    
    'faculty_submissions_list',
    'faculty_submission_bins_view',
    'review_submission',
    'mark_under_review_view',
    'mark_needs_revision_view',
    'mark_reviewed_view',
    'approve_selected_submissions_view',
    
    'preferences_view',
    'notification_settings_view',
    'account_and_security_view',
    'staff_permissions_view',
    
    'profile_view',
]

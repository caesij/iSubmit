from admin_staff_portal.views.core.dashboard_views import dashboard_view

from admin_staff_portal.views.core.document_repo_views import (
    document_repo_view,
    document_file_view,
)

from admin_staff_portal.views.core.submissions_views import (
    add_requirement,
    edit_requirement,
    requirements_list,
    toggle_requirement_status,
    
    faculty_submissions_list,
    faculty_submission_bins_view,
    review_submission,
    mark_under_review_view,
    mark_reviewed_view,
    approve_all_submissions_view,
)

from admin_staff_portal.views.core.user_mgmt_views import (
    user_list_view,
    user_create_view,
    user_update_view,
    user_toggle_acc_status_view,
)

from admin_staff_portal.views.general.settings_views import (
    preferences_view,
    notification_settings_view,
    account_and_security_view,
    staff_permissions_view,
)

from admin_staff_portal.views.general.profile_views import profile_view

__all__ = [
    'dashboard_view',
    
    'document_repo_view',
    'document_file_view',

    'add_requirement',
    'edit_requirement',
    'requirements_list',
    'toggle_requirement_status',
    
    'faculty_submissions_list',
    'faculty_submission_bins_view',
    'review_submission',
    'mark_under_review_view',
    'mark_reviewed_view',
    'approve_all_submissions_view',
    
    'user_list_view',
    'user_create_view',
    'user_update_view',
    'user_toggle_acc_status_view',
    
    'preferences_view',
    'notification_settings_view',
    'account_and_security_view',
    'staff_permissions_view',
    
    'profile_view',
]
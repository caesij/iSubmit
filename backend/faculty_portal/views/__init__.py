from faculty_portal.views.core.dashboard_views import dashboard_view

from faculty_portal.views.core.submission_bin_views import (
    upload_files_view,
    attach_document_view,
    replace_document_view,
    view_uploaded_document,
    confirm_submission,
    submission_complete,
)

from faculty_portal.views.core.my_submissions_views import (
    recent_submissions_list,
    view_my_submitted_document
)

from faculty_portal.views.core.my_documents_views import (
    all_documents_view,
    pinned_documents_view,
    toggle_pin_view,
    document_file_view,
)

from faculty_portal.views.general.settings_views import (
    preferences_view,
    notification_settings_view,
    notification_channel_view,
    account_and_security_view
)

from faculty_portal.views.general.profile_views import profile_view

__all__ = [
    'dashboard_view',
    
    'upload_files_view',
    'attach_document_view',
    'replace_document_view',
    'view_uploaded_document',
    'confirm_submission',
    'submission_complete',
    
    'recent_submissions_list',
    'view_my_submitted_document',
    
    'all_documents_view',
    'pinned_documents_view',
    'toggle_pin_view',
    'document_file_view',
    
    'preferences_view',
    'notification_settings_view',
    'notification_channel_view',
    'account_and_security_view',
    
    'profile_view',
]
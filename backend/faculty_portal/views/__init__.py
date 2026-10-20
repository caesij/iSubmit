from faculty_portal.views.core.dashboard_views import dashboard_view, dashboard_data_view

from faculty_portal.views.core.submission_bin_views import (
    submission_bin_data_view,
    submission_bins_view,
    attach_document,
    replace_document,
    remove_document,
    resubmit_document,
    submission_complete,
    view_document,
)

from faculty_portal.views.core.my_submissions_views import (
    submissions_list,
    submissions_data_view,
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
    'dashboard_data_view',
    
    'submission_bin_data_view',
    'submission_bins_view',
    'attach_document',
    'replace_document',
    'remove_document',
    'resubmit_document',
    'submission_complete',
    'view_document',

    'submissions_list',
    'submissions_data_view',
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
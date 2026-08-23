from faculty_portal.views.core.dashboard_views import DashboardView
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

__all__ = [
    'DashboardView',
    
    'upload_files_view',
    'attach_document_view',
    'replace_document_view',
    'view_uploaded_document',
    'confirm_submission',
    'submission_complete',
    
    'recent_submissions_list',
    'view_my_submitted_document',
]
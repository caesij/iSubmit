from admin_staff_portal.views.core.dashboard_views import DashboardView
from admin_staff_portal.views.core.user_mgmt_views import (
    UserListView,
    UserCreateView,
    UserUpdateView,
    UserToggleAccStatusView,
)
from .core.submissions_views import (
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

__all__ = [
    'DashboardView',
    'UserListView',
    'UserCreateView',
    'UserUpdateView',
    'UserToggleAccStatusView',
    
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
]
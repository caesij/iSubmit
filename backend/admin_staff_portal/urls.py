from django.urls import path
from admin_staff_portal import views

app_name = 'admin_staff_portal'

urlpatterns = [
    # Dashboard URL
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Document Repo URLs
    path('documents/document_repository/', views.document_repo_view, name='document_repo'),
    path('documents/<uuid:document_id>/view/', views.document_file_view, name='document_file_view'),
    
    # Requirement Management (Submission Bin) URLs
    path('submissions/submission_bins/', views.requirements_list, name='requirements_list'),
    path('submissions/submission_bins/add/', views.add_requirement, name='add_requirement'),
    path('submissions/submission_bins/<int:requirement_id>/edit/', views.edit_requirement, name='edit_requirement'),
    path('submissions/submission_bins/<int:requirement_id>/toggle-status/', views.toggle_requirement_status, name='toggle_requirement_status'),
    
    # Faculty Submission URLs
    path('submissions/faculty_submissions/faculty_submissions_list/', views.faculty_submissions_list, name='faculty_submissions_list'),
    path('submissions/faculty_submissions/faculty_submission_bins/<uuid:faculty_id>/', views.faculty_submission_bins_view, name='faculty_submission_bins_view'),
    path('submissions/faculty_submissions/review/<uuid:submission_id>', views.review_submission, name='review_submission'),
    path('faculty-submissions/<uuid:submission_id>/mark-under-review/', views.mark_under_review_view, name='mark_under_review'),
    path('faculty-submissions/<uuid:submission_id>/mark-reviewed/', views.mark_reviewed_view, name='mark_reviewed'),
    path('faculty-submissions/<uuid:faculty_id>/approve-all/', views.approve_all_submissions_view, name='approve_all_submissions'),
    
    # User Management URLs
    path('users/', views.user_list_view, name='user_list'),
    path('users/add/', views.user_create_view, name='user_create'),
    path('users/<uuid:pk>/edit/', views.user_update_view, name='user_edit'),
    path('users/<uuid:pk>/toggle-acc-status/', views.user_toggle_acc_status_view, name='user_toggle_acc_status'),
]
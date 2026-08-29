from django.urls import path
from faculty_portal import views

app_name = 'faculty_portal'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    
    # Submission Bin URLs
    path('submission_bin/upload_files/', views.upload_files_view, name='upload_files'),
    path('submission_bin/attach/<int:requirement_id>/', views.attach_document_view, name='attach_document'),
    path('submission_bin/replace/<uuid:document_id>/', views.replace_document_view, name='replace_document'),
    path('submission_bin/view/<uuid:document_id>/', views.view_uploaded_document, name='view_uploaded_document'),
    path('submission_bin/review_confirm/', views.confirm_submission, name='review_confirm'),
    path('submission_bin/submission_complete/', views.submission_complete, name='submission_complete'),
    
    # My Submissions URLs
    path('my_submissions/recent_submissions/', views.recent_submissions_list, name='recent_submissions'),
    path('my_submissions/recent_submissions/view/<uuid:document_id>/', views.view_my_submitted_document, name='view_my_submitted_document'),
    
    # My Documents URLs
    path('my_documents/', views.all_documents_view, name='my_documents'),
    path('my_documents/all_documents/', views.all_documents_view, name='all_documents'),
    path('my_documents/pinned_documents/', views.pinned_documents_view, name='pinned_documents'),
    path('my_documents/all_documents/<uuid:document_id>/view/', views.document_file_view, {'source': 'all'}, name='document_file_view_all'),
    path('my_documents/pinned_documents/<uuid:document_id>/view/', views.document_file_view, {'source': 'pinned'}, name='document_file_view_pinned'),
    path('my_documents/<uuid:document_id>/toggle-pin/', views.toggle_pin_view, name='toggle_pin')
]
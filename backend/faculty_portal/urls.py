from django.urls import path
from faculty_portal import views
from notifications.views import notification_list_view

app_name = 'faculty_portal'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/data/', views.dashboard_data_view, name='dashboard_data'),
    
    # Submission Bin URLs
    path('submission_bin/upload_files/', views.submission_bins_view, name='upload_files'),
    path('submission_bin/data/', views.submission_bin_data_view, name='submission_bin_data'),
    path('submission_bin/attach/<int:requirement_id>/', views.attach_document, name='attach_document'),
    path('submission_bin/replace/<uuid:document_id>/', views.replace_document, name='replace_document'),
    path('submission_bin/remove/<uuid:document_id>/', views.remove_document, name='remove_document'),
    path('submission_bin/resubmit/<uuid:submission_id>/', views.resubmit_document, name='resubmit_document'),
    path('submission_bin/submission_complete/', views.submission_complete, name='submission_complete'),
    path('submission_bin/view/<uuid:document_id>/', views.view_document, name='view_uploaded_document'),
    
    # My Submissions URLs
    path('my_submissions/submissions/', views.submissions_list, name='my_submissions'),
    path('my_submissions/submissions/data/', views.submissions_data_view, name='submissions_data'),
    path('my_submissions/submissions/view/<uuid:document_id>/', views.view_my_submitted_document, name='view_my_submitted_document'),
    
    # My Documents URLs
    path('my_documents/', views.all_documents_view, name='my_documents'),
    path('my_documents/all_documents/', views.all_documents_view, name='all_documents'),
    path('my_documents/pinned_documents/', views.pinned_documents_view, name='pinned_documents'),
    path('my_documents/all_documents/<uuid:document_id>/view/', views.document_file_view, {'source': 'all'}, name='document_file_view_all'),
    path('my_documents/pinned_documents/<uuid:document_id>/view/', views.document_file_view, {'source': 'pinned'}, name='document_file_view_pinned'),
    path('my_documents/<uuid:document_id>/toggle-pin/', views.toggle_pin_view, name='toggle_pin'),
    
    # Settings URLs
    path('settings/preferences/', views.preferences_view, name='preferences'),
    path('settings/notification_settings/', views.notification_settings_view, name='notification_settings'),
    path('settings/notification_channel/', views.notification_channel_view, name='notification_channel'),
    path('settings/account_and_security/', views.account_and_security_view, name='account_and_security'),
    
    # Profile URL
    path('profile/', views.profile_view, name='profile'),
    path('notifications/', notification_list_view, name='notifications'),
]
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

from accounts.decorators import admin, role_required
from accounts.forms import PreferencesForm
from accounts.models import NotificationPreference, StaffPermission
from accounts.utils import get_or_create_preferences

PERMISSION_FIELDS = [
    ('review_faculty_submissions', 'Review Faculty Submissions', 'Review submitted documents from faculty.'),
    ('return_for_revisions', 'Return for Revisions', 'Return submissions to faculty for revisions.'),
    ('create_submission_bins', 'Create Submission Bins', 'Create new submission bins for documents.'),
    ('edit_submission_bin', 'Edit Submission Bin', 'Edit details and settings for submission bins.'),
    ('view_approved_documents', 'View Approved Documents', 'View documents that have been approved.'),
    ('add_faculty_users', 'Add Faculty Users', 'Add new faculty users to the system.'),
]

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def preferences_view(request):
    if request.method == 'POST':
        form = PreferencesForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Preferences updated successfully.')
            return redirect('faculty_portal:preferences')
        else:
            messages.error(request, 'Invalid.')
    else:
        form = PreferencesForm(instance=request.user)

    context = {'form': form}
    
    return render(
        request,
        'faculty_portal/settings/preferences.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def notification_settings_view(request):
    preferences = get_or_create_preferences(request.user)

    if request.method == 'POST':
        for pref in preferences:
            pref.enabled = pref.notification_type in request.POST
            pref.email_enabled = f'email_{pref.notification_type}' in request.POST
            pref.system_enabled = f'system_{pref.notification_type}' in request.POST

        NotificationPreference.objects.bulk_update(
            preferences, ['enabled', 'email_enabled', 'system_enabled']
        )
        messages.success(request, 'Notification settings updated.')
        return redirect('admin_staff_portal:notification_settings')

    context = {'preferences': preferences}
    
    return render(
        request,
        'admin_staff_portal/core/settings/notification_settings.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def account_and_security_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('faculty_portal:account_and_security')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
        
    context = {'form': form}

    return render(
        request,
        'faculty_portal/settings/account_security.html',
        context
    )
    
@admin
@require_http_methods(['GET', 'POST'])
def staff_permissions_view(request):
    permissions = StaffPermission.get_solo()

    if request.method == 'POST':
        for field, _label, _desc in PERMISSION_FIELDS:
            setattr(permissions, field, field in request.POST)
        permissions.save()
        messages.success(request, 'Staff permissions updated.')
        return redirect('admin_staff_portal:staff_permissions')

    context = {
        'permissions': permissions,
        'permission_fields': PERMISSION_FIELDS,
    }
    
    return render(
        request,
        'admin_staff_portal/core/settings/staff_permissions.html',
        context
    )
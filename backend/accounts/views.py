from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model, login, logout
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.core.exceptions import PermissionDenied
from django.views.decorators.cache import never_cache

from accounts.forms import CustomLoginForm
from role_management.models import Role

from accounts.security import (
    DEVICE_COOKIE_NAME,
    DEVICE_COOKIE_MAX_AGE,
    assess_login_security,
    send_login_security_alert
)

from accounts.security import (
    revoke_current_login,
    revoke_login_record,
    revoke_other_logins
)

from accounts.models import SecurityLoginRecord

User = get_user_model()


def redirect_user_by_role(user):
    role = user.role
    role_code = role.code if role else None

    if role and role.is_faculty_role:
        preferred_dashboards = (('accounts.access_faculty_dashboard', 'faculty_portal:dashboard'),)

        fallback_pages = (
            ('accounts.access_faculty_submission_bin', 'faculty_portal:upload_files'),
            ('accounts.access_my_submissions', 'faculty_portal:my_submissions'),
            ('accounts.access_my_documents', 'faculty_portal:my_documents'),

            ('accounts.access_preferences', 'faculty_portal:preferences'),
            ('accounts.access_notification_settings', 'faculty_portal:notification_settings'),
            ('accounts.access_account_security', 'faculty_portal:account_and_security'),
            ('accounts.access_profile', 'faculty_portal:profile')
        )

    else:
        admin_dashboards = (
            ('accounts.access_admin_dashboard', 'admin_staff_portal:admin_dashboard'),
            ('accounts.access_staff_dashboard', 'admin_staff_portal:staff_dashboard')
        )

        staff_dashboards = (
            ('accounts.access_staff_dashboard', 'admin_staff_portal:staff_dashboard'),
            ('accounts.access_admin_dashboard', 'admin_staff_portal:admin_dashboard')
        )

        preferred_dashboards = {
            Role.Code.ADMIN: admin_dashboards,
            Role.Code.STAFF: staff_dashboards
        }.get(role_code, admin_dashboards)

        fallback_pages = (
            ('accounts.access_user_management', 'user_management:user_list'),
            ('accounts.access_program_management', 'programs:program_list'),
            ('accounts.access_submission_requirements', 'admin_staff_portal:requirements_list'),
            ('accounts.access_faculty_submissions', 'admin_staff_portal:faculty_submissions_list'),
            ('accounts.access_document_repository', 'admin_staff_portal:document_repo'),
            ('accounts.access_document_archive', 'admin_staff_portal:document_archive'),

            ('accounts.access_preferences', 'admin_staff_portal:preferences'),
            ('accounts.access_notification_settings', 'admin_staff_portal:notification_settings'),
            ('accounts.access_account_security', 'admin_staff_portal:account_and_security'),
            ('accounts.access_profile', 'admin_staff_portal:profile')
        )

    for permission, url_name in preferred_dashboards:
        if user.has_perm(permission):
            return redirect(url_name)

    for permission, url_name in fallback_pages:
        if user.has_perm(permission):
            return redirect(url_name)

    raise PermissionDenied('No page access has been configured for this account.')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            # Authenticate the user and establish the session
            login(request, user)

            # Assess whether a security alert is needed
            security_info = assess_login_security(request, user)

            # Resolve access before showing success; keep the existing permission rules.
            redirect_user_by_role(user)
            request.session['show_login_success'] = True
            response = redirect('accounts:login_success')

            if security_info is not None:
                response.set_cookie(
                    key=DEVICE_COOKIE_NAME,
                    value=security_info['device_token'],
                    max_age=DEVICE_COOKIE_MAX_AGE,
                    httponly=True,
                    secure=request.is_secure(),
                    samesite='Lax',
                    path='/'
                )

                send_login_security_alert(user, security_info)

            return response

        else:
            if form.non_field_errors():
                messages.error(
                    request,
                    'We could not sign you in. Please check your email and password.'
                )
            else:
                messages.error(
                    request,
                    'Invalid email or password.'
                )

            failed_attempts = getattr(request, 'axes_failures_since_start', None)

            if failed_attempts is not None:
                attempts_remaining = max(settings.AXES_FAILURE_LIMIT - failed_attempts,0)

                if attempts_remaining:
                    messages.warning(
                        request,
                        f"You have {attempts_remaining} sign-in attempt"
                        f"{'s' if attempts_remaining != 1 else ''} remaining."
                    )

    else:
        form = CustomLoginForm()
        
    context = {'form': form}

    return render(request, 'accounts/login.html', context)


@never_cache
@login_required
def login_success_view(request):
    destination = redirect_user_by_role(request.user)
    if not request.session.pop('show_login_success', False):
        return destination

    role = request.user.role
    return render(request, 'accounts/login_success.html', {
        'destination_url': destination.url,
        'role_name': role.get_code_display() if role.code else role.group.name,
        'is_dashboard': 'dashboard' in destination.url,
    })


def logout_view(request):
    if request.user.is_authenticated:
        revoke_current_login(
            request.user,
            request.session.session_key,
        )
    logout(request)
    return redirect('accounts:login')


def account_security_redirect(user):
    if user.is_faculty:
        return redirect('faculty_portal:account_and_security')
    return redirect('admin_staff_portal:account_and_security')


@login_required
def revoke_session_view(request, record_id):
    if request.method != 'POST':
        raise Http404

    current_session_key = request.session.session_key
    is_current = revoke_login_record(
        request.user,
        record_id,
        current_session_key,
    )
    if is_current:
        logout(request)
        return redirect('accounts:login')

    messages.success(request, 'The selected session was logged out.')
    return account_security_redirect(request.user)


@login_required
def revoke_other_sessions_view(request):
    if request.method != 'POST':
        raise Http404

    revoke_other_logins(request.user, request.session.session_key)
    messages.success(request, 'All other sessions were logged out.')
    return account_security_redirect(request.user)


@login_required
def revoke_selected_sessions_view(request):
    if request.method != 'POST':
        raise Http404

    current_session_key = request.session.session_key
    selected_ids = {
        value for value in request.POST.getlist('record_ids')
        if value.isdigit()
    }
    records = SecurityLoginRecord.objects.filter(
        user=request.user,
        id__in=selected_ids,
    ).exclude(session_key=current_session_key)

    for record_id in records.values_list('id', flat=True):
        revoke_login_record(request.user, record_id, current_session_key)

    messages.success(request, 'The selected sessions were logged out.')
    return account_security_redirect(request.user)

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404

from accounts.forms import CustomLoginForm
from accounts.utils import validate_portal_access

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


def redirect_user_by_role(user):
    if user.is_faculty:
        return redirect('faculty_portal:dashboard')
    elif user.is_admin:
        return redirect('admin_staff_portal:admin_dashboard')
    elif user.is_staff_role:
        return redirect('admin_staff_portal:staff_dashboard')
    return redirect('accounts:login')


def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)
    
    login_type = request.POST.get('login_type', 'ADMIN') if request.method == 'POST' else 'FACULTY'

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            is_allowed, error_msg = validate_portal_access(user, login_type)

            if not is_allowed:
                messages.error(request, error_msg)
                return render(request, 'accounts/login.html', {'form': form, 'login_type': login_type})
            
            # Determining whether a security alert is needed
            login(request, user)
            security_info = assess_login_security(request, user)

            response = redirect_user_by_role(user)

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
            for error in form.non_field_errors():
                messages.error(request, 'We could not sign you in. Please check your email and password.')
            if not form.non_field_errors():
                messages.error(request, 'Invalid email or password.')

            failed_attempts = getattr(request, 'axes_failures_since_start', None)
            if failed_attempts is not None:
                attempts_remaining = max(
                    settings.AXES_FAILURE_LIMIT - failed_attempts,
                    0,
                )
                if attempts_remaining:
                    messages.warning(
                        request,
                        f"You have {attempts_remaining} sign-in attempt"
                        f"{'s' if attempts_remaining != 1 else ''} remaining.",
                    )
    else:
        form = CustomLoginForm()
        
    context = {
        'form': form,
        'login_type': login_type
    }

    return render(request, 'accounts/login.html', context)


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
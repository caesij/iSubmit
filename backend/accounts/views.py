from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages

from accounts.forms import CustomLoginForm
from accounts.utils import validate_portal_access

from accounts.security import (
    DEVICE_COOKIE_NAME,
    DEVICE_COOKIE_MAX_AGE,
    assess_login_security,
    send_login_security_alert
)


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
            security_info = None

            if user.is_faculty:
                security_info = assess_login_security(request, user)

            login(request, user)

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
                messages.error(request, error)
            if not form.non_field_errors():
                messages.error(request, 'Invalid email or password.')
    else:
        form = CustomLoginForm()
        
    context = {
        'form': form,
        'login_type': login_type
    }

    return render(request, 'accounts/login.html', context)


def logout_view(request):
    logout(request)
    return redirect('accounts:login')
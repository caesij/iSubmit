from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib import messages
from .forms import CustomLoginForm
from .utils import validate_portal_access

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
            login(request, user)

            return redirect_user_by_role(user)

        else:
            for error in form.non_field_errors():
                messages.error(request, error)
            if not form.non_field_errors():
                messages.error(request, 'Invalid email or password.')
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form, 'login_type': login_type})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def redirect_user_by_role(user):
    if user.is_faculty:
        return redirect('faculty_portal:dashboard')
    elif user.is_admin or user.is_staff_role:
        return redirect('admin_staff_portal:dashboard')
    return redirect('accounts:login')
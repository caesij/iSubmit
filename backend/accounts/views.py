from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from accounts.models import User
from .forms import CustomLoginForm
from .utils import validate_portal_access

def login_view(request):
    if request.user.is_authenticated:
        return redirect_user_by_role(request.user)

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        login_type = request.POST.get('login_type', 'ADMIN')

        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user_obj = User.objects.filter(email=email).first()

            if user_obj and user_obj.check_password(password):
                # Account Status Validation
                if not user_obj.is_active:
                    messages.error(
                        request, 
                        "Your account has been deactivated. Please contact an administrator."
                    )
                    return render(request, 'accounts/login.html', {'form': form})

                # Permission Validation
                is_allowed, error_msg = validate_portal_access(user_obj, login_type)
                if not is_allowed:
                    messages.error(request, error_msg)
                    return render(request, 'accounts/login.html', {'form': form})

                user = authenticate(request, email=email, password=password)
                if user is not None:
                    login(request, user)
                    return redirect_user_by_role(user)

            # If user doesn't exist or password didn't match
            messages.error(request, "Invalid email or password.")
        else:
            messages.error(request, "Invalid email or password.")
    else:
        form = CustomLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


def redirect_user_by_role(user):
    if user.is_faculty:
        return redirect('faculty_portal:dashboard')
    elif user.is_admin or user.is_staff_role:
        return redirect('admin_staff_portal:dashboard')
    return redirect('accounts:login')
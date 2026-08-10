# For Future Use (Temporary)

from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

# For Faculty Views
def faculty_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_faculty:
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Faculty members.")
        return redirect('accounts:login')
    return _wrapped_view

# For Admin/Staff Views
def admin_or_staff_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated and (request.user.is_admin or request.user.is_staff_role):
            return view_func(request, *args, **kwargs)
        messages.error(request, "Access restricted to Admin and Staff members.")
        return redirect('accounts:login')
    return _wrapped_view
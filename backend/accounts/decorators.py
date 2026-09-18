from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from accounts.models import StaffPermission


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            user_role = getattr(request.user, 'role', None)
            
            if user_role not in roles:
                raise PermissionDenied('You do not have permission to access this page.')
                
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator

def admin(view_func):
    return role_required('ADMIN')(view_func)


def staff(view_func):
    return role_required('STAFF')(view_func)


def faculty(view_func):
    return role_required('FACULTY')(view_func)

def staff_permission_required(permission_field):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_admin:
                return view_func(request, *args, **kwargs)

            if request.user.is_staff_role:
                permissions = StaffPermission.get_solo()
                if not permissions.is_effectively_enabled(permission_field):
                    raise PermissionDenied(
                        'This action has been disabled for staff accounts by an administrator.'
                    )

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
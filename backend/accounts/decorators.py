from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


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
from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from role_management.permissions import OPERATION_PARENT_PAGES

def access_required(*permission_codenames):
    User = get_user_model()
    app_label = User._meta.app_label

    required_codes = list(dict.fromkeys(permission_codenames))

    for codename in permission_codenames:
        parent_page = OPERATION_PARENT_PAGES.get(codename)

        if parent_page and parent_page not in required_codes:
            required_codes.append(parent_page)

    permission_names = tuple(f'{app_label}.{codename}' for codename in required_codes)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not request.user.has_perms(permission_names):
                raise PermissionDenied('You do not have permission to perform this action.')

            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator


def superuser_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied('Only the system superuser can perform this action.')

        return view_func(request, *args, **kwargs)

    return _wrapped

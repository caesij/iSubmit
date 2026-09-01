from django.contrib.auth import get_user_model
from admin_staff_portal.forms import StaffManagementForm, FacultyManagementForm

User = get_user_model()

def get_target_role(request):
    role_param = (request.POST.get('role') or request.GET.get('role', '')).upper()

    if request.user.is_staff_role or role_param == User.Role.FACULTY:
        return User.Role.FACULTY
    return User.Role.STAFF


def get_page_title(target_role):
    return "Faculty Management" if target_role == User.Role.FACULTY else "Staff Management"


def get_form_class(target_role):
    return FacultyManagementForm if target_role == User.Role.FACULTY else StaffManagementForm


def get_form_template(target_role):
    if target_role == User.Role.FACULTY:
        return 'admin_staff_portal/core/user_mgmt/user_form_faculty.html'
    return 'admin_staff_portal/core/user_mgmt/user_form_staff.html'


def can_manage_target(request_user, target_user):
    if request_user.is_staff_role:
        return target_user.role == User.Role.FACULTY
    if request_user.is_admin:
        return target_user.role in [User.Role.STAFF, User.Role.FACULTY]
    return False

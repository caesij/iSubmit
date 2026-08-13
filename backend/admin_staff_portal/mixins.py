from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from admin_staff_portal.forms import StaffManagementForm, FacultyManagementForm
from django.shortcuts import redirect
from django.urls import reverse
from accounts.models import User

class AdminOrStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_admin or self.request.user.is_staff_role
        )

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            login_url = reverse('accounts:login')
            target_path = self.request.get_full_path()
            return redirect(f"{login_url}?next={target_path}")
        
        return super().handle_no_permission()

    def can_manage_target(self, target_user):
        user = self.request.user
        if user.is_staff_role:
            return target_user.role == User.Role.FACULTY
        if user.is_admin:
            return target_user.role in [User.Role.STAFF, User.Role.FACULTY]
        return False

class RoleContextMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)

        self.role_param = (
            request.POST.get('role') or 
            request.GET.get('role', '')
        ).upper()

        if request.user.is_authenticated and (request.user.is_staff_role or self.role_param == User.Role.FACULTY):
            self.target_role = User.Role.FACULTY
        else:
            self.target_role = User.Role.STAFF

    def get_page_title(self):
        return "Faculty Management" if self.target_role == User.Role.FACULTY else "Staff Management"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault('target_role', self.target_role)
        context.setdefault('current_role', self.target_role)
        context.setdefault('page_title', self.get_page_title())
        return context

class RoleFormMixin:
    def get_form_class(self):
        if self.target_role == User.Role.FACULTY:
            return FacultyManagementForm
        return StaffManagementForm

    def get_template_names(self):
        if self.target_role == User.Role.FACULTY:
            return ['admin_staff_portal/core/user_mgmt/user_form_faculty.html']
        return ['admin_staff_portal/core/user_mgmt/user_form_staff.html']

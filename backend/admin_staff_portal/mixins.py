from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.models import User

class AdminOrStaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and (
            self.request.user.is_admin or self.request.user.is_staff_role
        )

class RoleContextMixin:
    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.role_param = (
            request.GET.get('role') or 
            request.POST.get('role', '')
        ).upper()

        if request.user.is_authenticated and (request.user.is_staff_role or self.role_param == User.Role.FACULTY):
            self.target_role = User.Role.FACULTY
        else:
            self.target_role = User.Role.STAFF
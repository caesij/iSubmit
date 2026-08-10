from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from accounts.models import User

class FacultyRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role == User.Role.FACULTY
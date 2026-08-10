from django.views.generic import TemplateView
from faculty_portal.mixins import FacultyRequiredMixin

class DashboardView(FacultyRequiredMixin, TemplateView):
    template_name = 'faculty_portal/core/dashboard.html'
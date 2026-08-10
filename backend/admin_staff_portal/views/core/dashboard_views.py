from django.views.generic import TemplateView
from admin_staff_portal.mixins import AdminOrStaffRequiredMixin

class DashboardView(AdminOrStaffRequiredMixin, TemplateView):
    template_name = 'admin_staff_portal/core/dashboard.html'
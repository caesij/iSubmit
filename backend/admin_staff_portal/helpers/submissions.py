from django.contrib.auth import get_user_model

from faculty_portal.realtime import refresh_faculty_dashboard
from submissions.models import Requirement
from submissions.helpers import get_target_faculty_queryset


User = get_user_model()

def refresh_requirement_faculty_dashboards(old_requirement, new_requirement):
    faculty_qs = User.objects.filter(role=User.Role.FACULTY, is_active=True)
    old_ids = set(get_target_faculty_queryset(old_requirement).values_list('pk', flat=True))
    new_ids = set(get_target_faculty_queryset(new_requirement).values_list('pk', flat=True))

    for faculty_member in faculty_qs.filter(pk__in=old_ids | new_ids):
        refresh_faculty_dashboard(faculty_member)
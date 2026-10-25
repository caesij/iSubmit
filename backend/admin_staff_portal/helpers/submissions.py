from django.contrib.auth import get_user_model

from faculty_portal.realtime import refresh_faculty_dashboard
from submissions.models import Requirement


User = get_user_model()

def refresh_requirement_faculty_dashboards(old_assigned_to, new_assigned_to):
    faculty_qs = User.objects.filter(role=User.Role.FACULTY)

    faculty_ids = set()

    if old_assigned_to == Requirement.AssignedFacultyType.ALL:
        faculty_ids.update(faculty_qs.values_list('id', flat=True))
    else:
        faculty_ids.update(
            faculty_qs.filter(
                faculty_type=old_assigned_to
            ).values_list('id', flat=True)
        )

    if new_assigned_to == Requirement.AssignedFacultyType.ALL:
        faculty_ids.update(faculty_qs.values_list('id', flat=True))
    else:
        faculty_ids.update(
            faculty_qs.filter(
                faculty_type=new_assigned_to
            ).values_list('id', flat=True)
        )

    for faculty_member in faculty_qs.filter(id__in=faculty_ids):
        refresh_faculty_dashboard(faculty_member)
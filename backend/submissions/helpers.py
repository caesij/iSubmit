from django.contrib.auth import get_user_model
from django.db.models import Q

def get_target_faculty_queryset(requirement):
    User = get_user_model()

    faculty = User.objects.filter(role=User.Role.FACULTY, is_active=True)

    if not requirement.pk:
        return faculty.none()

    # Individual assignment filtering
    if requirement.assigned_faculty_member.exists():
        selected_faculty_ids = (requirement.assigned_faculty_member.values_list('pk', flat=True))

        return faculty.filter(pk__in=selected_faculty_ids).distinct()

    # Faculty type filtering
    if requirement.assigned_faculty_type in {'FULL_TIME', 'PART_TIME'}:
        faculty = faculty.filter(faculty_type=requirement.assigned_faculty_type)
    elif requirement.assigned_faculty_type != 'ALL':
        return faculty.none()

    # Program filtering
    if requirement.assigned_programs.exists():
        faculty = faculty.filter(
            assigned_programs__in=requirement.assigned_programs.values('pk')
        )

    return faculty.distinct()


# Get all requirements assigned to a given faculty member
def get_faculty_assigned_requirements(faculty):
    from submissions.models import Requirement

    individual_requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE,
        assigned_faculty_member=faculty,
    )

    group_requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE,
        assigned_faculty_member__isnull=True
    ).filter(
        Q(assigned_faculty_type=Requirement.AssignedFacultyType.ALL)
        | Q(assigned_faculty_type=faculty.faculty_type)
    ).filter(
        Q(assigned_programs__isnull=True)
        | Q(assigned_programs__in=faculty.assigned_programs.all())
    )

    return (group_requirements | individual_requirements).distinct()
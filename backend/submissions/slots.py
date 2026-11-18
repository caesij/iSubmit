from submissions.helpers import get_target_faculty_queryset
from submissions.models import (
    ClassAssignment,
    Requirement,
    UploadSlot,
    SubmissionPeriod
)

Unit = Requirement.Unit

UNIT_PARTS = {
    Unit.PER_SECTION: lambda a: (a.course_id, a.program_id, a.year_level, a.section),
    Unit.PER_YEAR_LEVEL: lambda a: (a.course_id, a.program_id, a.year_level, ''),
}
NO_CLASS = (None, None, None, '')


def calculate_expected_slots(requirements, assignments, faculty_ids):
    faculty_ids = set(faculty_ids)
    class_based = [r for r in requirements if r.unit != Unit.PER_FACULTY]
    faculty_wide = [r for r in requirements if r.unit == Unit.PER_FACULTY]

    from_classes = {
        (a.faculty_id, r.pk, *UNIT_PARTS[r.unit](a))
        for a in assignments if a.faculty_id in faculty_ids
        for r in class_based if r.applies_to_course(a.course)
    }
    
    from_faculty = {
        (faculty_id, r.pk, *NO_CLASS)
        for r in faculty_wide
        for faculty_id in faculty_ids
    }

    return from_classes | from_faculty


def sync_upload_slots(period):
    expected = calculate_expected_slots(
        requirements=Requirement.objects.filter(period=period),
        assignments=ClassAssignment.objects.filter(
            academic_year=period.academic_year, semester=period.semester
        ).select_related('course'),
        faculty_ids=get_target_faculty_queryset().values_list('pk', flat=True),
    )

    columns = ('faculty_id', 'requirement_id', 'course_id', 'program_id', 'year_level', 'section')
    existing = {
        row[:-1]: row[-1]
        for row in UploadSlot.objects.filter(requirement__period=period).values_list(*columns, 'pk')
    }

    UploadSlot.objects.bulk_create(
        [
            UploadSlot(**dict(zip(columns, parts)), key=UploadSlot.make_key(*parts[2:]))
            for parts in expected - existing.keys()
        ],
        ignore_conflicts=True,
    )

    stale_ids = [existing[parts] for parts in existing.keys() - expected]
    UploadSlot.objects.filter(pk__in=stale_ids, draft__isnull=True, submission__isnull=True).delete()
    
def sync_course_periods(course_id):

    terms = (
        ClassAssignment.objects
        .filter(course_id=course_id)
        .values_list('academic_year', 'semester')
        .distinct()
    )

    for academic_year, semester in terms:

        period = SubmissionPeriod.objects.filter(academic_year=academic_year, semester=semester).first()

        if period:
            sync_upload_slots(period)

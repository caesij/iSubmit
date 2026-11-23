from django.db.models import Count, Q

from programs.models import Program
from submissions.models import DocumentSubmission, UploadSlot


Status = DocumentSubmission.SubmissionStatus


def get_compliance_by_department(faculty):
    departments = {
        program['id']: {
            'program_id': program['id'],
            'program': program['program_name'],
            'faculty_count': 0,
            'fully_compliant_count': 0,
            'in_progress_count': 0,
            'not_submitted_count': 0,
            'compliance_percentage': 0,
        }
        for program in Program.objects.order_by('program_name').values(
            'id',
            'program_name',
        )
    }

    faculty_compliance = (
        UploadSlot.objects.active()
        .required()
        .filter(
            faculty__in=faculty,
            program__isnull=False,
        )
        .values('program_id', 'faculty_id')
        .annotate(
            total_slots=Count('pk'),
            completed_slots=Count(
                'submission',
                filter=(
                    Q(submission__isnull=False)
                    & ~Q(submission__status=Status.NEEDS_REVISION)
                ),
            ),
        )
        .order_by()
    )

    for row in faculty_compliance:
        department = departments.get(row['program_id'])

        if department is None:
            continue

        total_slots = row['total_slots']
        completed_slots = row['completed_slots']

        department['faculty_count'] += 1

        if completed_slots == total_slots:
            department['fully_compliant_count'] += 1

        elif completed_slots > 0:
            department['in_progress_count'] += 1

        else:
            department['not_submitted_count'] += 1

    results = []

    for department in departments.values():
        faculty_count = department['faculty_count']
        compliant_count = department['fully_compliant_count']

        if faculty_count:
            department['compliance_percentage'] = round(
                compliant_count / faculty_count * 100,
                1,
            )

        results.append(department)

    return results

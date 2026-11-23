from collections import OrderedDict
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone

from submissions.helpers import get_target_faculty_queryset
from submissions.models import DocumentSubmission, Requirement, UploadSlot
from admin_staff_portal.services.department_compliance import get_compliance_by_department

Status = DocumentSubmission.SubmissionStatus


def get_admin_dashboard_data():
    faculty = get_target_faculty_queryset()
    faculty_count = faculty.count()

    submissions = DocumentSubmission.objects.all()

    counts = submissions.aggregate(
        approved=Count('id', filter=Q(status=Status.APPROVED)),
        pending_approval=Count('id', filter=Q(status=Status.PENDING_APPROVAL)),
        submitted=Count('id', filter=Q(status__in=[
            Status.SUBMITTED,
            Status.RESUBMITTED,
            Status.UNDER_REVIEW,
            Status.PENDING_APPROVAL,
            Status.APPROVED,
        ])),
    )

    fully_compliant_count, in_progress_count, not_submitted_count = get_compliance_counts(faculty)

    documents_overview = (
        submissions
        .filter(
            faculty__in=faculty,
            status__in=[
                Status.APPROVED,
                Status.SUBMITTED,
                Status.RESUBMITTED,
                Status.PENDING_APPROVAL,
            ]
        )
        .select_related(
            'faculty',
            'faculty__faculty_profile',
            'requirement',
            'slot__course',
            'slot__program',
        )
        .order_by('-initially_submitted_at')[:5]
    )

    return {
        'faculty_count': faculty_count,
        'approved_count': counts['approved'],
        'submitted_count': counts['submitted'],
        'pending_approval_count': counts['pending_approval'],
        'active_requirement_count': Requirement.objects.active().count(),

        'fully_compliant_count': fully_compliant_count,
        'in_progress_count': in_progress_count,
        'not_submitted_count': not_submitted_count,

        'fully_compliant_percentage': percentage(fully_compliant_count, faculty_count),
        'in_progress_percentage': percentage(in_progress_count, faculty_count),
        'not_submitted_percentage': percentage(not_submitted_count, faculty_count),

        'documents_overview': documents_overview,
        'submission_trends': get_submission_trends(submissions),
        
        'compliance_by_department': get_compliance_by_department(faculty),
    }


def percentage(count, total):
    return round(count / total * 100) if total else 0


def get_compliance_counts(faculty):
    # Returns (fully compliant, in progress, not submitted) as numbers of faculty members

    # fully compliant: every upload they owe is submitted
    # in progress:     some of the uploads they owe are submitted, not all
    # not submitted:   none of the uploads they owe is submitted
    
    # Faculty who owe no uploads are skipped
    
    rows = list(UploadSlot.objects.filter(faculty__in=faculty).progress_by_faculty())

    fully_compliant = sum(1 for row in rows if row['completed'] == row['total'])
    not_submitted = sum(1 for row in rows if row['completed'] == 0)

    return fully_compliant, len(rows) - fully_compliant - not_submitted, not_submitted


def get_submission_trends(submissions):
    today = timezone.localdate()
    months = []

    for index in range(5, -1, -1):
        month_date = today.replace(day=1)

        for _ in range(index):
            month_date = (month_date - timedelta(days=1)).replace(day=1)

        months.append(month_date)

    results = OrderedDict()

    for month in months:
        next_month = (month.replace(day=28) + timedelta(days=4)).replace(day=1)

        count = submissions.filter(
            initially_submitted_at__gte=month,
            initially_submitted_at__lt=next_month,
        ).count()

        results[month.strftime('%b')] = count

    return [{'month': month, 'count': count} for month, count in results.items()]

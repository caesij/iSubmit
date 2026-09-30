from django.db.models import Q
from django.utils import timezone
from django.utils.formats import date_format

from submissions.models import Requirement, DocumentSubmission


def get_dashboard_data(user):

    active_requirements = (
        Requirement.objects
        .filter(
            status=Requirement.ReqStatus.ACTIVE
        )
        .filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            |
            Q(assigned_to=user.faculty_type)
        )
    )

    total_requirements = active_requirements.count()

    submissions = DocumentSubmission.objects.filter(
        faculty=user,
        requirement__in=active_requirements,
    )

    total_submitted_count = (
        submissions
        .values('requirement_id')
        .distinct()
        .count()
    )

    approved_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).count()

    submitted_count = submissions.filter(
        status__in=[
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED,
        ]
    ).count()

    under_review_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    ).count()

    pending_approval_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    ).count()

    returned_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
    ).count()
    
    deadline_queryset = (
        active_requirements
        .filter(
            deadline__isnull=False,
            deadline__gte=timezone.now(),
        )
        .order_by("deadline")[:5]
    )

    upcoming_deadlines = [
        {
            "requirement_title": requirement.requirement_title,
            "deadline": date_format(
                requirement.deadline,
                "M j, Y"
            ),
        }
        for requirement in deadline_queryset
    ]

    def percentage(count):

        if not total_requirements:
            return 0

        return round(
            (count / total_requirements) * 100
        )

    return {
        'total_requirements': total_requirements,
        'total_submitted_count': total_submitted_count,
        'approved_count': approved_count,
        'submitted_count': submitted_count,
        'under_review_count': under_review_count,
        'pending_approval_count': pending_approval_count,
        'returned_count': returned_count,
        'upcoming_deadlines': upcoming_deadlines,

        'approved_pct': percentage(approved_count),
        'submitted_pct': percentage(submitted_count),
        'under_review_pct': percentage(under_review_count),
        'pending_approval_pct': percentage(pending_approval_count),
        'returned_pct': percentage(returned_count),
    }
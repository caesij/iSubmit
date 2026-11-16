from django.db.models import Count, Q
from django.utils import timezone
from core.date_formatting import format_display_date

from submissions.models import DocumentSubmission, SubmissionPeriod, UploadSlot
from submissions.querysets import active_document_queryset

Status = DocumentSubmission.SubmissionStatus


def get_dashboard_data(user):
    owed = UploadSlot.objects.active().required().filter(faculty=user)
    total_requirements = owed.count()

    submissions = active_document_queryset().filter(faculty=user, slot__in=owed)

    counts = submissions.aggregate(
        approved_count=Count('id', filter=Q(status=Status.APPROVED)),
        submitted_count=Count('id', filter=Q(status__in=[Status.SUBMITTED, Status.RESUBMITTED])),
        under_review_count=Count('id', filter=Q(status=Status.UNDER_REVIEW)),
        pending_approval_count=Count('id', filter=Q(status=Status.PENDING_APPROVAL)),
        returned_count=Count('id', filter=Q(status=Status.NEEDS_REVISION)),
        total_submitted_count=Count('id', filter=Q(status__in=[
            Status.APPROVED,
            Status.SUBMITTED,
            Status.RESUBMITTED,
            Status.UNDER_REVIEW,
            Status.PENDING_APPROVAL,
        ])),
    )

    def percentage(count):
        return round(count / total_requirements * 100) if total_requirements else 0

    return {
        'total_requirements': total_requirements,
        **counts,
        'upcoming_deadlines': get_upcoming_deadlines(owed, user),
        'approved_pct': percentage(counts['approved_count']),
        'submitted_pct': percentage(counts['submitted_count']),
        'under_review_pct': percentage(counts['under_review_count']),
        'pending_approval_pct': percentage(counts['pending_approval_count']),
        'returned_pct': percentage(counts['returned_count']),
    }


def get_upcoming_deadlines(owed, user):
    rows = list(
        owed
        .filter(requirement__period__deadline__gte=timezone.now())
        .filter(Q(submission__isnull=True) | Q(submission__status=Status.NEEDS_REVISION))
        .values('requirement__period')
        .annotate(left=Count('pk'))
        .order_by('requirement__period__deadline')[:5]
    )
    periods = SubmissionPeriod.objects.in_bulk(row['requirement__period'] for row in rows)

    return [
        {
            'title': f"{periods[row['requirement__period']]} ({row['left']} left)",
            'deadline': format_display_date(periods[row['requirement__period']].deadline, user),
        }
        for row in rows
    ]

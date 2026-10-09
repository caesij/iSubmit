from django.utils.formats import date_format

from submissions.models import DocumentSubmission

def get_overview_queryset(user, tab='all'):
    overview_qs = (
        DocumentSubmission.objects
        .filter(faculty=user)
        .select_related('requirement')
        .order_by('-initially_submitted_at')
    )

    if tab == 'approved':
        overview_qs = overview_qs.filter(
            status=DocumentSubmission.SubmissionStatus.APPROVED
        )

    elif tab == 'submitted':
        overview_qs = overview_qs.filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
            ]
        )

    elif tab == 'under_review':
        overview_qs = overview_qs.filter(
            status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
        )

    elif tab == 'pending_approval':
        overview_qs = overview_qs.filter(
            status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
        )

    elif tab == 'returned':
        overview_qs = overview_qs.filter(
            status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
        )

    return overview_qs


def serialize_overview_submissions(overview_qs):
    return [
        {
            'title': submission.requirement.requirement_title,
            'date': date_format(
                submission.initially_submitted_at, 'M j, Y'
            ),
            'time': date_format(
                submission.initially_submitted_at, 'g:i A'
            ),
            'status': submission.status,
        }
        for submission in overview_qs[:5]
    ]
from submissions.models import DocumentSubmission


def get_staff_dashboard_data():
    submissions = DocumentSubmission.objects.select_related('faculty', 'requirement')

    assigned_count = submissions.count()

    under_review_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    ).count()

    returned_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
    ).count()

    final_review_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    ).count()

    approved_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).count()

    reviewed_count = (
        returned_count
        + final_review_count
        + approved_count
    )

    review_progress = (
round((reviewed_count / assigned_count) * 100)
        if assigned_count
        else 0
    )

    review_queue = (
        submissions
        .filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
                DocumentSubmission.SubmissionStatus.UNDER_REVIEW
            ]
        )
        .order_by('-initially_submitted_at')[:5]
    )

    return {
        'assigned_count': assigned_count,
        'under_review_count': under_review_count,
        'returned_count': returned_count,
        'final_review_count': final_review_count,
        'approved_count': approved_count,
        'review_progress': review_progress,
        'review_queue': review_queue
    }
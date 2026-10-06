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

    completed_reviews_count = submissions.filter(
        status__in=[
            DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
            DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
            DocumentSubmission.SubmissionStatus.APPROVED,
        ]
    ).count()

    pending_review_count = submissions.filter(
        status__in=[
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED,
            DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
        ]
    ).count()

    review_total = (
        completed_reviews_count
        + pending_review_count
    )

    review_progress = (
        round((completed_reviews_count / review_total) * 100)
        if review_total
        else 0
    )

    pending_review_progress = (
        100 - review_progress
        if review_total
        else 0
    )

    review_queue = (
        submissions
        .filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
                DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
            ]
        )
        .order_by('-initially_submitted_at')[:5]
    )

    return {
        'assigned_count': assigned_count,
        'under_review_count': under_review_count,
        'returned_count': returned_count,
        'completed_reviews_count': completed_reviews_count,
        'pending_review_count': pending_review_count,
        'review_progress': review_progress,
        'pending_review_progress': pending_review_progress,
        'review_queue': review_queue,
    }
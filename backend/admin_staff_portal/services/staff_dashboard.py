from collections import OrderedDict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from submissions.models import DocumentSubmission
from submissions.querysets import active_document_queryset

User = get_user_model()


def get_staff_dashboard_data():
    faculty_count = User.objects.filter(role=User.Role.FACULTY, is_active=True).count()

    submissions = active_document_queryset().select_related('faculty', 'requirement')
    
    pending_review_statuses = [
        DocumentSubmission.SubmissionStatus.SUBMITTED,
        DocumentSubmission.SubmissionStatus.RESUBMITTED,
        DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
    ]
    
    reviewed_statuses = [
        DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
        DocumentSubmission.SubmissionStatus.APPROVED,
    ]

    completed_reviews_count = submissions.filter(status__in=reviewed_statuses).count()

    submitted_count = submissions.count()

    under_review_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    ).count()

    returned_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
    ).count()

    pending_review_count = submissions.filter(
        status__in=pending_review_statuses
    ).count()

    review_total = completed_reviews_count + pending_review_count

    review_progress = round((completed_reviews_count / review_total) * 100) if review_total else 0
    pending_review_progress = 100 - review_progress if review_total else 0

    documents_overview = (
        submissions
        .filter(
            faculty__role=User.Role.FACULTY,
            faculty__is_active=True,
            status__in=[
                DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
                DocumentSubmission.SubmissionStatus.NEEDS_REVISION
            ]
        )
        .select_related('faculty', 'requirement')
        .order_by('-initially_submitted_at')[:5]
    )

    trends = get_submission_trends(submissions)

    return {
        'faculty_count': faculty_count,
        'completed_reviews_count': completed_reviews_count,
        'submitted_count': submitted_count,
        'under_review_count': under_review_count,
        'returned_count': returned_count,
        'pending_review_count': pending_review_count,
        
        'review_progress': review_progress,
        'pending_review_progress': pending_review_progress,
        
        'documents_overview': documents_overview,
        'submission_trends': trends,
    }


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
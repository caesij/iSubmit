from collections import OrderedDict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from submissions.models import Requirement, DocumentSubmission

User = get_user_model()

def get_admin_dashboard_data():
    faculty_count = User.objects.filter(
        role=User.Role.FACULTY
    ).count()

    active_requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE
    )

    active_requirement_count = active_requirements.count()

    submissions = DocumentSubmission.objects.all()

    submitted_count = submissions.count()

    approved_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).count()

    final_review_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    ).count()

    total_possible_submissions = (
        faculty_count * active_requirement_count
    )

    if total_possible_submissions:
        compliance = round(
            (approved_count / total_possible_submissions) * 100
        )
    else:
        compliance = 0

    pending_review = (
        submissions
        .filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
                DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
                DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
            ]
        )
        .select_related(
            'faculty',
            'requirement',
        )
        .order_by(
            '-initially_submitted_at'
        )[:5]
    )

    trends = get_submission_trends(submissions)

    return {
        'faculty_count': faculty_count,
        'submitted_count': submitted_count,
        'approved_count': approved_count,
        'final_review_count': final_review_count,
        'active_requirement_count': active_requirement_count,
        'compliance': compliance,
        'pending_review': pending_review,
        'submission_trends': trends
    }


def get_submission_trends(submissions):
    today = timezone.localdate()
    months = []

    for index in range(5, -1, -1):
        month_date = today.replace(day=1)

        for _ in range(index):
            month_date = (
                month_date - timedelta(days=1)
            ).replace(day=1)

        months.append(month_date)

    results = OrderedDict()

    for month in months:
        next_month = (
            month.replace(day=28)
            + timedelta(days=4)
        ).replace(day=1)

        count = submissions.filter(
            initially_submitted_at__gte=month,
            initially_submitted_at__lt=next_month
        ).count()

        results[month.strftime('%b')] = count

    return [
        {
            'month': month,
            'count': count
        }
        for month, count in results.items()
    ]
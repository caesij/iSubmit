from collections import OrderedDict
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from submissions.models import Requirement, DocumentSubmission

User = get_user_model()


def get_admin_dashboard_data():
    faculty = list(
        User.objects
        .filter(role=User.Role.FACULTY)
        .only('id', 'faculty_type')
    )
    
    active_requirements = list(
        Requirement.objects
        .filter(status=Requirement.ReqStatus.ACTIVE)
        .only('id', 'assigned_to')
    )
    
    submissions = DocumentSubmission.objects.all()

    faculty_count = len(faculty)
    approved_count = submissions.filter(status=DocumentSubmission.SubmissionStatus.APPROVED).count()
    submitted_count = submissions.count()
    pending_approval_count = submissions.filter(status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL).count()
    active_requirement_count = len(active_requirements)

    faculty_ids = [user.id for user in faculty]
    active_requirement_ids = [requirement.id for requirement in active_requirements]

    submitted_bins = {}

    if faculty_ids and active_requirement_ids:
        submission_rows = (
            submissions
            .filter(faculty_id__in=faculty_ids, requirement_id__in=active_requirement_ids)
            .values('faculty_id', 'requirement_id')
            .distinct()
        )

        for row in submission_rows:
            submitted_bins.setdefault(row['faculty_id'], set()).add(row['requirement_id'])

    approved_bins = {}

    if faculty_ids and active_requirement_ids:
        approved_rows = (
            submissions
            .filter(
                faculty_id__in=faculty_ids,
                requirement_id__in=active_requirement_ids,
                status=DocumentSubmission.SubmissionStatus.APPROVED,
            )
            .values('faculty_id', 'requirement_id')
            .distinct()
        )

        for row in approved_rows:
            approved_bins.setdefault(row['faculty_id'], set()).add(row['requirement_id'])

    fully_compliant_count = 0
    in_progress_count = 0
    not_submitted_count = 0

    for user in faculty:
        assigned_requirements = [
            requirement
            for requirement in active_requirements
            if requirement.assigned_to in (
                Requirement.AssignedFacultyType.ALL,
                user.faculty_type,
            )
        ]

        assigned_requirement_ids = {requirement.id for requirement in assigned_requirements}

        if not assigned_requirement_ids:
            continue

        user_submitted_bins = submitted_bins.get(user.id, set()) & assigned_requirement_ids
        user_approved_bins = approved_bins.get(user.id, set()) & assigned_requirement_ids

        total_assigned = len(assigned_requirement_ids)
        submitted_total = len(user_submitted_bins)
        approved_total = len(user_approved_bins)

        if approved_total == total_assigned:
            fully_compliant_count += 1
        elif submitted_total > 0:
            in_progress_count += 1
        else:
            not_submitted_count += 1

    fully_compliant_percentage = (round((fully_compliant_count / faculty_count) * 100) if faculty_count else 0)

    in_progress_percentage = (round((in_progress_count / faculty_count) * 100) if faculty_count else 0)

    not_submitted_percentage = (round((not_submitted_count / faculty_count) * 100) if faculty_count else 0)

    pending_review = (
        submissions
        .filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED
            ]
        )
        .select_related('faculty', 'requirement')
        .order_by('-initially_submitted_at')[:5]
    )

    trends = get_submission_trends(submissions)

    return {
        'faculty_count': faculty_count,
        'approved_count': approved_count,
        'submitted_count': submitted_count,
        'pending_approval_count': pending_approval_count,
        'active_requirement_count': active_requirement_count,

        'fully_compliant_count': fully_compliant_count,
        'in_progress_count': in_progress_count,
        'not_submitted_count': not_submitted_count,

        'fully_compliant_percentage': fully_compliant_percentage,
        'in_progress_percentage': in_progress_percentage,
        'not_submitted_percentage': not_submitted_percentage,

        'pending_review': pending_review,
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
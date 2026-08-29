from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone

from accounts.decorators import faculty
from submissions.models import Requirement, DocumentSubmission

@faculty
@require_http_methods(['GET'])
def dashboard_view(request):
    active_requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE
    ).filter(
        Q(assigned_to=Requirement.AssignedFacultyType.ALL) |
        Q(assigned_to=request.user.faculty_type)
    )

    total_requirements = active_requirements.count()

    submissions = DocumentSubmission.objects.filter(
        faculty=request.user,
        requirement__in=active_requirements,
    ).select_related('requirement')

    approved_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).count()
    submitted_count = submissions.filter(
        status__in=[
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED,
        ]
    ).count()
    pending_count = submissions.filter(
        status__in=[
            DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
            DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
        ]
    ).count()
    returned_count = submissions.filter(
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
    ).count()

    def pct(count):
        return round((count / total_requirements) * 100) if total_requirements else 0

    submitted_requirement_ids = submissions.values_list('requirement_id', flat=True)
    upcoming_deadlines = active_requirements.exclude(
        id__in=submitted_requirement_ids
    ).filter(
        deadline__gte=timezone.now()
    ).order_by('deadline')[:4]

    tab = request.GET.get('tab', 'all')
    overview_qs = submissions.order_by('-initially_submitted_at')
    if tab == 'approved':
        overview_qs = overview_qs.filter(status=DocumentSubmission.SubmissionStatus.APPROVED)
    elif tab == 'submitted':
        overview_qs = overview_qs.filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
            ]
        )
    elif tab == 'pending':
        overview_qs = overview_qs.filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.UNDER_REVIEW,
                DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
            ]
        )

    context = {
        'total_requirements': total_requirements,
        'approved_count': approved_count,
        'submitted_count': submitted_count,
        'pending_count': pending_count,
        'returned_count': returned_count,
        'approved_pct': pct(approved_count),
        'submitted_pct': pct(submitted_count),
        'pending_pct': pct(pending_count),
        'returned_pct': pct(returned_count),
        'upcoming_deadlines': upcoming_deadlines,
        'overview_submissions': overview_qs[:5],
        'selected_tab': tab,
    }

    return render(
        request, 
        'faculty_portal/core/dashboard.html', 
        context)
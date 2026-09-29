from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from accounts.decorators import faculty
from faculty_portal.services import get_dashboard_data
from submissions.models import DocumentSubmission

@faculty
@require_http_methods(['GET'])
def dashboard_data_view(request):
    data = get_dashboard_data(request.user)

    return JsonResponse(data)

@faculty
@require_http_methods(['GET'])
def dashboard_view(request):
    data = get_dashboard_data(request.user)

    tab = request.GET.get('tab', 'all')
    overview_qs = DocumentSubmission.objects.filter(
        faculty=request.user
    ).select_related('requirement').order_by('-initially_submitted_at')

    if tab == 'approved':
        overview_qs = overview_qs.filter(status=DocumentSubmission.SubmissionStatus.APPROVED)
    elif tab == 'submitted':
        overview_qs = overview_qs.filter(
            status__in=[
                DocumentSubmission.SubmissionStatus.SUBMITTED,
                DocumentSubmission.SubmissionStatus.RESUBMITTED,
            ]
        )
    elif tab == 'under_review':
        overview_qs = overview_qs.filter(status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW)
    elif tab == 'pending_approval':
        overview_qs = overview_qs.filter(status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL)
    elif tab == 'returned':
        overview_qs = overview_qs.filter(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)

    context = {
        **data,
        'overview_submissions': overview_qs[:5],
        'selected_tab': tab,
    }
    return render(request, 'faculty_portal/core/dashboard.html', context)
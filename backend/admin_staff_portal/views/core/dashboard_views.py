from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse

from accounts.decorators import role_required
from admin_staff_portal.services import get_admin_dashboard_data

@role_required('ADMIN')
@require_http_methods(['GET'])
def admin_dashboard_data_view(request):
    data = get_admin_dashboard_data()

    pending_review = []

    for submission in data['pending_review']:
        pending_review.append({
            'id': str(submission.id),
            'faculty': submission.faculty.get_full_name(),
            'document': submission.requirement.requirement_title,
            'date': (
                submission.initially_submitted_at.strftime(
                    '%b %d, %Y'
                ).replace(' 0', ' ')
                if submission.initially_submitted_at
                else ''
            ),
            'status': submission.status,
        })

    return JsonResponse({
        'faculty_count': data['faculty_count'],
        'submitted_count': data['submitted_count'],
        'approved_count': data['approved_count'],
        'final_review_count': data['final_review_count'],
        'active_requirement_count': data['active_requirement_count'],
        'compliance': data['compliance'],
        'submission_trends': data['submission_trends'],
        'pending_review': pending_review,
    })

@role_required('ADMIN')
@require_http_methods(['GET'])
def admin_dashboard_view(request):
    context = get_admin_dashboard_data()

    return render(
        request,
        'admin_staff_portal/core/admin_dashboard.html',
        context
    )
    
@role_required('STAFF')
@require_http_methods(['GET'])
def staff_dashboard_view(request):

    return render(
        request,
        'admin_staff_portal/core/staff_dashboard.html',
    )
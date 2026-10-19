from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from django.http import JsonResponse

from accounts.decorators import role_required
from admin_staff_portal.services.admin_dashboard import get_admin_dashboard_data
from admin_staff_portal.services.staff_dashboard import get_staff_dashboard_data
from core.date_formatting import format_display_date

@role_required('ADMIN')
@require_http_methods(['GET'])
def admin_dashboard_data_view(request):
    data = get_admin_dashboard_data()

    documents_overview = []

    for submission in data['documents_overview']:
        latest_submission_date = (submission.resubmitted_at or submission.initially_submitted_at)

        documents_overview.append({
            'faculty_id': submission.faculty.id,
            'faculty': submission.faculty.get_full_name(),
            'faculty_type': submission.faculty.get_faculty_type_display(),
            'bin_title': submission.requirement.requirement_title,
            'latest_submission_date': format_display_date(
                latest_submission_date,
                request.user,
            ),
            'status': submission.status,
            'faculty_bins_url': reverse(
                'admin_staff_portal:faculty_submission_bins_view',
                args=[submission.faculty.id]
            )
        })

    return JsonResponse({
        'faculty_count': data['faculty_count'],
        'approved_count': data['approved_count'],
        'submitted_count': data['submitted_count'],
        'pending_approval_count': data['pending_approval_count'],
        'active_requirement_count': data['active_requirement_count'],

        'fully_compliant_count': data['fully_compliant_count'],
        'in_progress_count': data['in_progress_count'],
        'not_submitted_count': data['not_submitted_count'],

        'fully_compliant_percentage': data['fully_compliant_percentage'],
        'in_progress_percentage': data['in_progress_percentage'],
        'not_submitted_percentage': data['not_submitted_percentage'],

        'submission_trends': data['submission_trends'],
        'documents_overview': documents_overview,
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
def staff_dashboard_data_view(request):
    data = get_staff_dashboard_data()

    documents_overview = []
    
    for submission in data['documents_overview']:
        latest_submission_date = (submission.resubmitted_at or submission.initially_submitted_at)

        documents_overview.append({
            'faculty_id': submission.faculty.id,
            'faculty': submission.faculty.get_full_name(),
            'faculty_type': submission.faculty.get_faculty_type_display(),
            'bin_title': submission.requirement.requirement_title,
            'latest_submission_date': format_display_date(
                latest_submission_date,
                request.user,
            ),
            'status': submission.status,
            'faculty_bins_url': reverse(
                'admin_staff_portal:faculty_submission_bins_view',
                args=[submission.faculty.id]
            )
        })

    return JsonResponse({
        'faculty_count': data['faculty_count'],
        'submitted_count': data['submitted_count'],
        'completed_reviews_count': data['completed_reviews_count'],
        'under_review_count': data['under_review_count'],
        'returned_count': data['returned_count'],
        'pending_review_count': data['pending_review_count'],
        
        'review_progress': data['review_progress'],
        'pending_review_progress': data['pending_review_progress'],
        
        'submission_trends': data['submission_trends'],
        'documents_overview': documents_overview
    })


@role_required('STAFF')
@require_http_methods(['GET'])
def staff_dashboard_view(request):
    context = get_staff_dashboard_data()

    return render(
        request,
        'admin_staff_portal/core/staff_dashboard.html',
        context
    )
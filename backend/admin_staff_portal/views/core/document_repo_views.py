from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.core.paginator import Paginator

from accounts.decorators import role_required
from submissions.models import Requirement, DocumentSubmission

User = get_user_model()

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def document_repo_view(request):
    submissions = DocumentSubmission.objects.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).select_related('requirement', 'faculty')

    if not submissions.exists():
        messages.info(request, 'No approved documents to show')

    semester = request.GET.get('semester')
    academic_term = request.GET.get('academic_term')
    faculty_type = request.GET.get('faculty')
    sort_by = request.GET.get('sort_by', 'newest')

    if semester:
        submissions = submissions.filter(requirement__semester=semester)
    if academic_term:
        submissions = submissions.filter(requirement__academic_term=academic_term)
    if faculty_type:
        submissions = submissions.filter(faculty__faculty_type=faculty_type)

    if sort_by == 'oldest':
        submissions = submissions.order_by('initially_submitted_at')
    else:
        submissions = submissions.order_by('-initially_submitted_at')

    paginator = Paginator(submissions, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'semesters': Requirement.Semester.choices,
        'academic_terms': Requirement.objects.values_list(
            'academic_term', flat=True
        ).distinct().order_by('-academic_term'),
        'faculty_type_choices': [
            c for c in Requirement.AssignedFacultyType.choices if c[0] != 'ALL'
        ],
        'selected_semester': semester or '',
        'selected_academic_term': academic_term or '',
        'selected_faculty_type': faculty_type or '',
        'selected_sort_by': sort_by,
    }

    return render(
        request,
        'admin_staff_portal/core/documents/document_repo.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def document_file_view(request, document_id):
    document = get_object_or_404(
        DocumentSubmission.objects.select_related('requirement', 'faculty'),
        pk=document_id,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    )
    
    context = {'document': document}
    
    return render(
        request,
        'admin_staff_portal/core/documents/document_file_view.html',
        context
    )
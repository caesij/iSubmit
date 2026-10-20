from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required
from submissions.models import DocumentSubmission, Requirement
from submissions.doc_search import search_documents


@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def document_repo_view(request):
    submissions = DocumentSubmission.objects.filter(
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).select_related('requirement', 'faculty')

    semester = request.GET.get('semester', '')
    academic_term = request.GET.get('academic_term', '')
    faculty_type = request.GET.get('faculty_type', '')
    sort_by = request.GET.get('sort_by', 'newest')
    search_query = request.GET.get('q', '').strip()

    if semester:
        submissions = submissions.filter(requirement__semester=semester)
    if academic_term:
        submissions = submissions.filter(requirement__academic_term=academic_term)
    if faculty_type:
        submissions = submissions.filter(faculty__faculty_type=faculty_type)
    if search_query:
        submissions = search_documents(submissions, search_query, sort_by)
    else:
        submissions = submissions.order_by(
            'initially_submitted_at' if sort_by == 'oldest' else '-initially_submitted_at'
        )
    
    if not submissions.exists():
        messages.info(request, "No approved documents match your filters.")

    page_obj = Paginator(submissions, 7).get_page(request.GET.get("page"))
    return render(request, 'admin_staff_portal/core/documents/document_repo.html', {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'semesters': Requirement.Semester.choices,
        'academic_terms': Requirement.objects.values_list(
            'academic_term', flat=True
        ).distinct().order_by('-academic_term'),
        'faculty_type_choices': [
            choice for choice in Requirement.AssignedFacultyType.choices
            if choice[0] != 'ALL'
        ],
        'selected_semester': semester,
        'selected_academic_term': academic_term,
        'selected_faculty_type': faculty_type,
        'selected_sort_by': sort_by,
        'search_query': search_query,
    })


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
from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import faculty
from submissions.models import DocumentSubmission, Requirement
from submissions.doc_search import search_documents


def _render_repository(request, submissions, template_name, academic_term, document_type):
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort_by', 'newest')

    if academic_term:
        submissions = submissions.filter(requirement__academic_term=academic_term)
    if document_type:
        submissions = submissions.filter(
            document_file__iendswith=f'.{document_type.lower()}'
        )
    if search_query:
        submissions = search_documents(submissions, search_query, sort_by)
    else:
        submissions = submissions.order_by(
            'initially_submitted_at' if sort_by == 'oldest' else '-initially_submitted_at'
        )
    
    if not submissions.exists():
        messages.info(request, "No documents match your filters.")

    page_obj = Paginator(submissions, 7).get_page(request.GET.get('page'))
    return render(request, template_name, {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'academic_terms': Requirement.objects.values_list(
            'academic_term', flat=True
        ).distinct().order_by('-academic_term'),
        'document_type_choices': ['PDF', 'DOC', 'DOCX', 'XLSX'],
        'selected_academic_term': academic_term,
        'selected_document_type': document_type,
        'selected_sort_by': sort_by,
        'search_query': search_query,
    })


@faculty
@require_http_methods(['GET'])
def all_documents_view(request):
    submissions = DocumentSubmission.objects.filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).select_related('requirement')
    
    return _render_repository(
        request, submissions,
        'faculty_portal/core/my_documents/all_documents.html',
        request.GET.get('academic_term', ''),
        request.GET.get('document_type', '')
    )


@faculty
@require_http_methods(['GET'])
def pinned_documents_view(request):
    submissions = DocumentSubmission.objects.filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        is_pinned=True
    ).select_related('requirement')
    
    return _render_repository(
        request, submissions,
        'faculty_portal/core/my_documents/pinned_documents.html',
        request.GET.get('academic_term', ''),
        request.GET.get('document_type', '')
    )


@faculty
@require_http_methods(['POST'])
def toggle_pin_view(request, document_id):
    document = get_object_or_404(DocumentSubmission, pk=document_id, faculty=request.user)
    
    document.is_pinned = not document.is_pinned
    document.save(update_fields=['is_pinned'])
    return redirect(request.META.get('HTTP_REFERER', 'faculty_portal:all_documents'))


@faculty
@require_http_methods(['GET'])
def document_file_view(request, document_id, source='all'):
    document = get_object_or_404(
        DocumentSubmission.objects.select_related('requirement'),
        pk=document_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    )
    
    if source == 'pinned':
        back_url_name, breadcrumb_label = 'faculty_portal:pinned_documents', 'Pinned Documents'
    else:
        back_url_name, breadcrumb_label = 'faculty_portal:all_documents', 'All Documents'
        
    context = {
        'document': document,
        'back_url_name': back_url_name,
        'breadcrumb_label': breadcrumb_label
    }
    
    return render(
        request,
        'faculty_portal/core/my_documents/document_file_view.html',
        context
    )
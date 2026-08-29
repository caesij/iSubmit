from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.core.paginator import Paginator

from accounts.decorators import faculty
from submissions.models import Requirement, DocumentSubmission

@faculty
@require_http_methods(['GET'])
def all_documents_view(request):
    submissions = DocumentSubmission.objects.filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).select_related('requirement')
    
    if not submissions.exists():
        messages.info(request, 'No approved documents to show')
        
    academic_term = request.GET.get('academic_term')
    document_type = request.GET.get('document_type')
    sort_by = request.GET.get('sort_by', 'newest')
    
    if academic_term:
        submissions = submissions.filter(requirement__academic_term=academic_term)
    if document_type:
        submissions = submissions.filter(document_file__iendswith=f'.{document_type.lower()}')
        
    if sort_by ==  'oldest':
        submissions = submissions.order_by('initially_submitted_at')
    else:
        submissions = submissions.order_by('-initially_submitted_at')
        
    paginator = Paginator(submissions, 7)
    page_obj = paginator.get_page(request.GET.get('page'))
        
    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'academic_terms': Requirement.objects.values_list(
            'academic_term', flat=True
        ).distinct().order_by('-academic_term'),
        'document_type_choices': ['PDF', 'DOC', 'DOCX', 'XLSX'],
        'selected_academic_term': academic_term or '',
        'selected_document_type': document_type or '',
        'selected_sort_by': sort_by
    }
    
    return render(
        request,
        'faculty_portal/core/my_documents/all_documents.html', 
        context
    )

@faculty
@require_http_methods(['GET'])
def pinned_documents_view(request):
    submissions = DocumentSubmission.objects.filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        is_pinned=True
    ).select_related('requirement')
        
    if not submissions.exists():
        messages.info(request, 'No pinned documents to show')
        
    academic_term = request.GET.get('academic_term')
    document_type = request.GET.get('document_type')
    sort_by = request.GET.get('sort_by', 'newest')
    
    if academic_term:
        submissions = submissions.filter(requirement__academic_term=academic_term)
    if document_type:
        submissions = submissions.filter(document_file__iendswith=f'.{document_type.lower()}')
        
    if sort_by ==  'oldest':
        submissions = submissions.order_by('initially_submitted_at')
    else:
        submissions = submissions.order_by('-initially_submitted_at')
        
    paginator = Paginator(submissions, 7)
    page_obj = paginator.get_page(request.GET.get('page'))
        
    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'academic_terms': Requirement.objects.values_list(
            'academic_term', flat=True
        ).distinct().order_by('-academic_term'),
        'document_type_choices': ['PDF', 'DOC', 'DOCX', 'XLSX'],
        'selected_academic_term': academic_term or '',
        'selected_document_type': document_type or '',
        'selected_sort_by': sort_by
    }
    
    return render(
        request,
        'faculty_portal/core/my_documents/pinned_documents.html', 
        context
    )
    
@faculty
@require_http_methods(['POST'])
def toggle_pin_view(request, document_id):
    document = get_object_or_404(
        DocumentSubmission,
        pk=document_id,
        faculty=request.user
    )
    
    document.is_pinned = not document.is_pinned
    document.save(update_fields=['is_pinned'])
    
    return redirect(request.META.get('HTTP_REFERER', 'faculty_portal:all_documents_view'))

@faculty
@require_http_methods(['GET'])
def document_file_view(request, document_id, source='all'):
    document = get_object_or_404(
        DocumentSubmission,
        pk=document_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    )

    if source == 'pinned':
        back_url_name = 'faculty_portal:pinned_documents'
        breadcrumb_label = 'Pinned Documents'
    else:
        back_url_name = 'faculty_portal:all_documents'
        breadcrumb_label = 'All Documents'

    context = {
        'document': document,
        'back_url_name': back_url_name,
        'breadcrumb_label': breadcrumb_label,
    }
    return render(
        request,
        'faculty_portal/core/my_documents/document_file_view.html',
        context
    )
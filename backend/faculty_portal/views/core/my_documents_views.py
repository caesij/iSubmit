from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from faculty_portal.helpers.my_documents import _render_repository
from accounts.decorators import faculty
from submissions.models import DocumentSubmission
from submissions.querysets import active_document_queryset

TEMPLATE_DIR = 'faculty_portal/core/my_documents'

@faculty
@require_http_methods(['GET'])
def all_documents_view(request):
    submissions = active_document_queryset().filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED
    ).select_related('requirement')

    return _render_repository(
        request, submissions,
        f'{TEMPLATE_DIR}/all_documents.html',
        request.GET.get('academic_year', ''),
        request.GET.get('document_type', '')
    )


@faculty
@require_http_methods(['GET'])
def pinned_documents_view(request):
    submissions = active_document_queryset().filter(
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        is_pinned=True
    ).select_related('requirement')

    return _render_repository(
        request, submissions,
        f'{TEMPLATE_DIR}/pinned_documents.html',
        request.GET.get('academic_year', ''),
        request.GET.get('document_type', '')
    )


@faculty
@require_http_methods(['POST'])
def toggle_pin_view(request, document_id):
    document = get_object_or_404(
        active_document_queryset(),
        pk=document_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
    )

    document.is_pinned = not document.is_pinned
    document.save(update_fields=['is_pinned'])
    return redirect(request.META.get('HTTP_REFERER', 'faculty_portal:all_documents'))


@faculty
@require_http_methods(['GET'])
def document_file_view(request, document_id, source='all'):
    document = get_object_or_404(
        active_document_queryset().select_related('requirement'),
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
        f'{TEMPLATE_DIR}/document_file_view.html',
        context
    )
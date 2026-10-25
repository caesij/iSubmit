import logging
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from accounts.decorators import admin, role_required
from submissions.models import DocumentSubmission
from admin_staff_portal.realtime import refresh_document_surfaces
from faculty_portal.realtime import refresh_faculty_submission_bin

from admin_staff_portal.helpers.document_repo import (
    render_document_list,
    _document_redirect,
    _selected_ids
)

logger = logging.getLogger(__name__)

TEMPLATE_DIR = 'admin_staff_portal/core/documents'

User = get_user_model()

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def document_repo_view(request):
    return render_document_list(
        request,
        template_name=f'{TEMPLATE_DIR}/document_repo.html',
    )


@role_required('ADMIN')
@require_http_methods(['GET'])
def document_archive_view(request):
    return render_document_list(
        request,
        template_name=f'{TEMPLATE_DIR}/document_archive.html',
        archived=True,
    )


@admin
@require_http_methods(['POST'])
def bulk_archive_document_view(request):
    document_ids = _selected_ids(request)
    if not document_ids:
        messages.warning(request, 'Select at least one document to archive.')
        return _document_redirect(False)

    now = timezone.now()
    documents = DocumentSubmission.objects.filter(
        id__in=document_ids,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        is_archived=False,
    )
    faculty_ids = list(documents.values_list('faculty_id', flat=True))
    updated = documents.update(
        is_archived=True,
        archived_at=now,
        archive_expires_at=now + timedelta(days=30),
    )
    refresh_document_surfaces(faculty_ids)
    messages.success(request, f'{updated} document(s) archived.')
    return _document_redirect(False)


@admin
@require_http_methods(['POST'])
def bulk_restore_document_view(request):
    document_ids = _selected_ids(request)
    if not document_ids:
        messages.warning(request, 'Select at least one document to restore.')
        return _document_redirect(True)

    documents = DocumentSubmission.objects.filter(
        id__in=document_ids,
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        is_archived=True,
        archive_expires_at__gt=timezone.now(),
    )
    faculty_ids = list(documents.values_list('faculty_id', flat=True))
    updated = documents.update(
        is_archived=False,
        archived_at=None,
        archive_expires_at=None,
    )
    refresh_document_surfaces(faculty_ids)
    messages.success(request, f'{updated} document(s) restored.')
    return _document_redirect(True)


@admin
@require_http_methods(['POST'])
def bulk_permanently_delete_document_view(request):
    document_ids = _selected_ids(request)
    if not document_ids:
        messages.warning(request, 'Select at least one document to delete.')
        return _document_redirect(True)

    with transaction.atomic():
        documents = list(DocumentSubmission.objects.select_for_update().filter(
            id__in=document_ids,
            status=DocumentSubmission.SubmissionStatus.APPROVED,
            is_archived=True,
        ))
        faculty_ids = [document.faculty_id for document in documents]
        storage = DocumentSubmission._meta.get_field('document_file').storage
        file_names = [document.document_file.name for document in documents]

        try:
            for file_name in filter(None, file_names):
                storage.delete(file_name)
        except Exception:
            logger.exception('Could not delete selected archived document files.')
            messages.error(
                request,
                'One or more cloud files could not be deleted. No records were removed.',
            )
            return _document_redirect(True)

        DocumentSubmission.objects.filter(id__in=[document.id for document in documents]).delete()
        
        for faculty in User.objects.filter(pk__in=set(faculty_ids)):
            refresh_faculty_submission_bin(faculty)

    refresh_document_surfaces(faculty_ids)

    messages.success(request, f'{len(documents)} document(s) permanently deleted.')
    return _document_redirect(True)


@admin
@require_http_methods(['POST'])
def archive_document_view(request, document_id):
    request.POST = request.POST.copy()
    request.POST.setlist('document_ids', [str(document_id)])
    return bulk_archive_document_view(request)


@admin
@require_http_methods(['POST'])
def restore_document_view(request, document_id):
    request.POST = request.POST.copy()
    request.POST.setlist('document_ids', [str(document_id)])
    return bulk_restore_document_view(request)


@admin
@require_http_methods(['POST'])
def permanently_delete_document_view(request, document_id):
    request.POST = request.POST.copy()
    request.POST.setlist('document_ids', [str(document_id)])
    return bulk_permanently_delete_document_view(request)


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
        f'{TEMPLATE_DIR}/document_file_view.html',
        context
    )

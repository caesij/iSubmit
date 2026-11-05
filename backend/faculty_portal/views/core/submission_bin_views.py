from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from submissions.helpers import get_target_faculty_queryset
from django.views.decorators.http import require_http_methods

from accounts.decorators import role_required

from faculty_portal.helpers.submission_bin import (
    UPLOAD_PAGE,
    cancel_extraction,
    delete_file_after_commit,
    dispatch_pending_extractions,
    load_upload_rows,
    process_submission,
    retry_extraction,
    save_draft_form
)

from submissions.models import (
    DocumentMetadata,
    DocumentSubmission,
    DraftUpload,
    Requirement
)
from submissions.querysets import active_document_queryset

TEMPLATE_DIR = 'faculty_portal/core/submission_bin'

@role_required('FACULTY')
@require_http_methods(['GET'])
def submission_bin_data_view(request):
    response = render(
        request,
        f'{TEMPLATE_DIR}/_upload_rows.html',
        {'rows': load_upload_rows(request.user)},
    )
    response['Cache-Control'] = 'no-store'
    return response


@role_required('FACULTY')
@require_http_methods(['GET', 'POST'])
def submission_bins_view(request):
    if request.method == 'POST' and request.POST.get('action') == 'submit':
        return process_submission(request)

    context = {'rows': load_upload_rows(request.user)}

    return render(
        request,
        f'{TEMPLATE_DIR}/upload_files.html',
        context
    )


@role_required('FACULTY')
@require_http_methods(['POST'])
def attach_document(request, requirement_id):
    requirement = get_object_or_404(
        Requirement,
        pk=requirement_id,
        status=Requirement.ReqStatus.ACTIVE,
        deadline__gt=timezone.now(),
    )

    if not get_target_faculty_queryset(requirement).filter(pk=request.user.pk).exists():
        return HttpResponseForbidden('This requirement is not available for your account.')

    draft, _ = DraftUpload.objects.select_related('requirement').get_or_create(faculty=request.user, requirement=requirement)

    return save_draft_form(
        request,
        draft,
        success_message='File attached successfully.',
        error_message='We could not attach that file. Please check the file type and size, then try again.'
    )


@role_required('FACULTY')
@require_http_methods(['POST'])
def replace_document(request, document_id):
    draft = get_object_or_404(
        DraftUpload.objects.select_related('requirement'),
        pk=document_id,
        faculty=request.user,
        requirement__deadline__gt=timezone.now(),
    )

    return save_draft_form(
        request,
        draft,
        success_message='File replaced successfully.',
        error_message='We could not replace that file. Please check the file type and size, then try again.',
    )


@role_required('FACULTY')
@require_http_methods(['POST'])
def remove_document(request, document_id):
    draft = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user,
        requirement__deadline__gt=timezone.now(),
    )

    if not draft.draft_file:
        messages.info(request, 'There is no file to remove.')
        return redirect(UPLOAD_PAGE)

    old_file_name = draft.draft_file.name
    old_storage = draft.draft_file.storage
    metadata = DocumentMetadata.objects.filter(draft=draft).first()
    if metadata:
        cancel_extraction(metadata.pk, metadata.text_extraction_request_id)

    with transaction.atomic():
        DocumentMetadata.objects.filter(draft=draft).delete()
        delete_file_after_commit(old_storage, old_file_name)
        draft.delete()
        transaction.on_commit(
            lambda: dispatch_pending_extractions(request.user.pk)
        )

    messages.success(request, 'File removed successfully.')
    return redirect(UPLOAD_PAGE)


@role_required('FACULTY')
@require_http_methods(['POST'])
def retry_document_extraction(request, document_id):
    draft = get_object_or_404(
        DraftUpload.objects.select_related('requirement'),
        pk=document_id,
        faculty=request.user,
        requirement__deadline__gt=timezone.now(),
    )

    if not draft.draft_file:
        messages.error(request, 'Upload a file before retrying text extraction.')
        return redirect(UPLOAD_PAGE)

    retry_extraction(draft)
    messages.success(request, 'Text extraction was queued again.')
    return redirect(UPLOAD_PAGE)


@role_required('FACULTY')
@require_http_methods(['POST'])
def resubmit_document(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission.objects.select_related('requirement'),
        pk=submission_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
        requirement__deadline__gt=timezone.now(),
    )

    draft, _ = DraftUpload.objects.select_related('requirement').get_or_create(
        faculty=request.user,
        requirement=submission.requirement
    )

    return save_draft_form(
        request,
        draft,
        success_message='Replacement file uploaded. Select it and submit it when ready.',
        error_message='We could not replace that file. Please check the file type and size, then try again.'
    )


@role_required('FACULTY')
@require_http_methods(['GET'])
def submission_complete(request):
    submitted_ids = request.session.pop('recently_submitted_ids', [])

    submitted_documents = list(
        active_document_queryset()
        .filter(faculty=request.user, id__in=submitted_ids)
        .select_related('requirement')
        .order_by('-initially_submitted_at')
    )

    if not submitted_documents:
        messages.info(request, 'No recent submission to show.')
        return redirect(UPLOAD_PAGE)
    
    context = {'submitted_documents': submitted_documents}

    return render(
        request,
        f'{TEMPLATE_DIR}/submission_complete.html',
        context
    )


@role_required('FACULTY')
@require_http_methods(['GET'])
def view_document(request, document_id):
    uploaded_document = get_object_or_404(
        DraftUpload.objects.select_related('requirement', 'document_metadata'),
        pk=document_id,
        faculty=request.user,
        requirement__deadline__gt=timezone.now(),
    )
    
    context = {
        'uploaded_document': uploaded_document,
        'metadata': getattr(uploaded_document, 'document_metadata', None),
    }

    return render(
        request,
        f'{TEMPLATE_DIR}/view_uploaded_document.html',
        context
    )
from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import faculty

from faculty_portal.helpers.submission_bin import (
    UPLOAD_PAGE,
    delete_file_after_commit,
    load_upload_rows,
    process_submission,
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

@faculty
@require_http_methods(['GET'])
def submission_bin_data_view(request):
    response = render(
        request,
        f'{TEMPLATE_DIR}/_upload_rows.html',
        {'rows': load_upload_rows(request.user)},
    )
    response['Cache-Control'] = 'no-store'
    return response


@faculty
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


@faculty
@require_http_methods(['POST'])
def attach_document(request, requirement_id):
    requirement = get_object_or_404(
        Requirement,
        pk=requirement_id,
        status=Requirement.ReqStatus.ACTIVE
    )

    allowed_types = (Requirement.AssignedFacultyType.ALL, request.user.faculty_type)
    if requirement.assigned_to not in allowed_types:
        return HttpResponseForbidden('This requirement is not available for your account.')

    draft, _ = DraftUpload.objects.select_related('requirement').get_or_create(faculty=request.user, requirement=requirement)

    return save_draft_form(
        request,
        draft,
        success_message='File attached successfully.',
        error_message='We could not attach that file. Please check the file type and size, then try again.'
    )


@faculty
@require_http_methods(['POST'])
def replace_document(request, document_id):
    draft = get_object_or_404(
        DraftUpload.objects.select_related('requirement'),
        pk=document_id,
        faculty=request.user
    )

    return save_draft_form(
        request,
        draft,
        success_message='File replaced successfully.',
        error_message='We could not replace that file. Please check the file type and size, then try again.',
    )


@faculty
@require_http_methods(['POST'])
def remove_document(request, document_id):
    draft = get_object_or_404(DraftUpload, pk=document_id, faculty=request.user)

    if not draft.draft_file:
        messages.info(request, 'There is no file to remove.')
        return redirect(UPLOAD_PAGE)

    old_file_name = draft.draft_file.name
    old_storage = draft.draft_file.storage

    with transaction.atomic():
        draft.draft_file = ''
        draft.save(update_fields=['draft_file', 'draft_updated_at'])
        DocumentMetadata.objects.filter(draft=draft).delete()
        delete_file_after_commit(old_storage, old_file_name)

    messages.success(request, 'File removed successfully.')
    return redirect(UPLOAD_PAGE)


@faculty
@require_http_methods(['POST'])
def resubmit_document(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission.objects.select_related('requirement'),
        pk=submission_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION
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


@faculty
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


@faculty
@require_http_methods(['GET'])
def view_document(request, document_id):
    uploaded_document = get_object_or_404(DraftUpload, pk=document_id, faculty=request.user)
    
    context = {'uploaded_document': uploaded_document}

    return render(
        request,
        f'{TEMPLATE_DIR}/view_uploaded_document.html',
        context
    )
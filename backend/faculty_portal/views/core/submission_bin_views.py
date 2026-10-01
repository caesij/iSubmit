from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction

from accounts.decorators import faculty
from faculty_portal.helpers.submission_bin_helpers import (
    run_ocr_if_enabled,
    get_available_requirements,
    get_drafts_by_requirement,
    get_needs_revision_by_requirement,
    build_upload_rows,
    process_submission,
    save_draft_form,
    apply_resubmission,
)

from submissions.models import (
    Requirement,
    DraftUpload,
    DocumentSubmission,
)
from submissions.forms import DocumentRevisionForm


@faculty
@require_http_methods(['GET', 'POST'])
def upload_files_view(request):
    requirements = get_available_requirements(request.user)
    drafts_by_requirement = get_drafts_by_requirement(request.user, requirements)

    if request.method == 'POST' and request.POST.get('action') == 'submit':
        return process_submission(request, requirements, drafts_by_requirement)

    needs_revision_by_requirement = get_needs_revision_by_requirement(
        request.user,
        requirements,
    )

    rows = build_upload_rows(
        requirements,
        drafts_by_requirement,
        needs_revision_by_requirement,
    )

    context = {'rows': rows}

    return render(
        request,
        'faculty_portal/core/submission_bin/upload_files.html',
        context,
    )


@faculty
@require_http_methods(['POST'])
def attach_document_view(request, requirement_id):
    requirement = get_object_or_404(
        Requirement,
        pk=requirement_id,
        status=Requirement.ReqStatus.ACTIVE,
    )

    if requirement.assigned_to not in (
        Requirement.AssignedFacultyType.ALL,
        request.user.faculty_type,
    ):
        return HttpResponseForbidden('You are not assigned to this requirement.')

    draft, _ = DraftUpload.objects.get_or_create(
        faculty=request.user,
        requirement=requirement,
    )

    return save_draft_form(
        request,
        draft,
        success_message='File attached successfully.',
        error_message='Failed to upload file. Please check the format and size.',
    )


@faculty
@require_http_methods(['POST'])
def replace_document_view(request, document_id):
    draft = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user,
    )

    return save_draft_form(
        request,
        draft,
        success_message='File replaced successfully.',
        error_message='Failed to replace file.',
    )


@faculty
@require_http_methods(['GET'])
def submission_complete(request):
    submitted_ids = request.session.pop('recently_submitted_ids', [])

    submitted_documents = (
        DocumentSubmission.objects
        .filter(faculty=request.user, id__in=submitted_ids)
        .select_related('requirement')
        .order_by('-initially_submitted_at')
    )

    if not submitted_documents.exists():
        messages.info(request, 'No recent submission to show.')
        return redirect('faculty_portal:upload_files')

    context = {'submitted_documents': submitted_documents}

    return render(
        request,
        'faculty_portal/core/submission_bin/submission_complete.html',
        context
    )


@faculty
@require_http_methods(['GET'])
def view_uploaded_document(request, document_id):
    uploaded_document = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user,
    )

    context = {'uploaded_document': uploaded_document}

    return render(
        request,
        'faculty_portal/core/submission_bin/view_uploaded_document.html',
        context
    )


@faculty
@require_http_methods(['POST'])
def resubmit_document_view(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission,
        pk=submission_id,
        faculty=request.user,
        status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
    )

    form = DocumentRevisionForm(request.POST, request.FILES)

    if not form.is_valid():
        messages.error(request, 'Failed to resubmit. Please check the file format and size.')
        return redirect('faculty_portal:upload_files')

    try:
        with transaction.atomic():
            apply_resubmission(submission, form.cleaned_data['file'])

        messages.success(request, 'Document resubmitted successfully.')

    except Exception as e:
        print('RESUBMISSION ERROR:', repr(e))

        messages.error(
            request,
            'An error occurred while processing your resubmission. Please try again.',
        )

    return redirect('faculty_portal:upload_files')


@faculty
@require_http_methods(['POST'])
def remove_document_view(request, document_id):
    draft = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user
    )

    if draft.draft_file:
        draft.draft_file.delete(save=False)
        draft.draft_file = ''
        draft.save(update_fields=['draft_file', 'draft_updated_at'])
        messages.success(request, 'File removed successfully.')
    else:
        messages.info(request, 'There is no file to remove.')

    return redirect('faculty_portal:upload_files')
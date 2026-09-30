from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.db import transaction
from django.core.files.base import ContentFile

from accounts.decorators import faculty
from submissions.models import (
    Requirement,
    DraftUpload,
    DocumentSubmission,
    DocumentRevision,
)
from submissions.forms import DraftUploadForm, DocumentRevisionForm


@faculty
@require_http_methods(['GET'])
def upload_files_view(request):
    already_submitted_ids = (
        DocumentSubmission.objects
        .filter(faculty=request.user)
        .exclude(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)
        .values_list('requirement_id', flat=True)
    )

    requirements = (
        Requirement.objects
        .filter(status=Requirement.ReqStatus.ACTIVE)
        .filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            | Q(assigned_to=request.user.faculty_type)
        )
        .exclude(id__in=already_submitted_ids)
        .order_by('deadline')
    )

    drafts_by_requirement = {
        draft.requirement_id: draft
        for draft in DraftUpload.objects.filter(
            faculty=request.user,
            requirement__in=requirements
        )
    }

    needs_revision_by_requirement = {
        submission.requirement_id: submission
        for submission in (
            DocumentSubmission.objects
            .filter(
                faculty=request.user,
                requirement__in=requirements,
                status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
            )
            .select_related('requirement')
            .prefetch_related('revisions__reviews')
        )
    }

    rows = []

    for requirement in requirements:
        submission = needs_revision_by_requirement.get(requirement.id)
        draft = drafts_by_requirement.get(requirement.id)

        rows.append({
            'requirement': requirement,
            'draft': draft,
            'submission': submission,
            'needs_revision_submission': submission,
            'is_resubmission': bool(submission),
        })

    context = {'rows': rows}

    return render(
        request,
        'faculty_portal/core/submission_bin/upload_files.html',
        context
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
        request.user.faculty_type
    ):
        return HttpResponseForbidden('You are not assigned to this requirement.')

    draft, _ = DraftUpload.objects.get_or_create(
        faculty=request.user,
        requirement=requirement
    )

    form = DraftUploadForm(
        request.POST,
        request.FILES,
        instance=draft
    )

    if form.is_valid():
        form.save()
        messages.success(request, 'File attached successfully.')
    else:
        messages.error(
            request,
            'Failed to upload file. Please check the format and size.'
        )

    return redirect('faculty_portal:upload_files')


@faculty
@require_http_methods(['POST'])
def replace_document_view(request, document_id):
    draft = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user
    )

    form = DraftUploadForm(
        request.POST,
        request.FILES,
        instance=draft
    )

    if form.is_valid():
        form.save()
        messages.success(request, 'File replaced successfully.')
    else:
        messages.error(request, 'Failed to replace file.')

    return redirect('faculty_portal:upload_files')


@faculty
@require_http_methods(['GET', 'POST'])
def confirm_submission(request):
    already_submitted_ids = (
        DocumentSubmission.objects
        .filter(faculty=request.user)
        .values_list('requirement_id', flat=True)
    )

    requirements = (
        Requirement.objects
        .filter(status=Requirement.ReqStatus.ACTIVE)
        .filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            | Q(assigned_to=request.user.faculty_type)
        )
        .exclude(id__in=already_submitted_ids)
        .order_by('deadline')
    )

    if not requirements.exists():
        request.session.pop('selected_submission_ids', None)
        messages.warning(request, 'You have no active requirements to submit.')
        return redirect('faculty_portal:upload_files')

    drafts_by_requirement = {
        draft.requirement_id: draft
        for draft in DraftUpload.objects.filter(
            faculty=request.user,
            requirement__in=requirements,
        )
    }

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'review':
            selected_ids = request.POST.getlist('selected_requirements')

            valid_ids = {str(requirement.id) for requirement in requirements}
            selected_ids = [value for value in selected_ids if value in valid_ids]

            if not selected_ids:
                messages.error(
                    request,
                    'Please select at least one document to continue.',
                )
                return redirect('faculty_portal:upload_files')

            selected_rows = []

            for requirement in requirements:
                if str(requirement.id) not in selected_ids:
                    continue

                draft = drafts_by_requirement.get(requirement.id)

                selected_rows.append({
                    'requirement': requirement,
                    'draft': draft,
                    'is_ready': bool(draft and draft.draft_file),
                })

            if any(not row['is_ready'] for row in selected_rows):
                messages.error(
                    request,
                    'All selected documents must have an attached file.',
                )
                return redirect('faculty_portal:upload_files')

            request.session['selected_submission_ids'] = selected_ids

            return redirect('faculty_portal:review_confirm')

        if action == 'submit':
            selected_ids = request.session.get('selected_submission_ids', [])

            if not selected_ids:
                messages.error(request, 'No documents were selected for submission.')
                return redirect('faculty_portal:upload_files')

            valid_ids = {str(requirement.id) for requirement in requirements}
            selected_ids = [value for value in selected_ids if value in valid_ids]

            if not selected_ids:
                request.session.pop('selected_submission_ids', None)
                messages.error(
                    request,
                    'The selected documents are no longer available.',
                )
                return redirect('faculty_portal:upload_files')

            selected_rows = []

            for requirement in requirements:
                if str(requirement.id) not in selected_ids:
                    continue

                draft = drafts_by_requirement.get(requirement.id)

                selected_rows.append({
                    'requirement': requirement,
                    'draft': draft,
                    'is_ready': bool(draft and draft.draft_file),
                })

            if not selected_rows:
                messages.error(request, 'No valid documents were selected.')
                return redirect('faculty_portal:upload_files')

            if any(not row['is_ready'] for row in selected_rows):
                messages.error(
                    request,
                    'One or more selected documents do not have an attached file.',
                )
                return redirect('faculty_portal:upload_files')

            try:
                completed_submissions = []

                with transaction.atomic():
                    for row in selected_rows:
                        draft = row['draft']

                        draft.draft_file.open('rb')
                        file_content = ContentFile(draft.draft_file.read())
                        original_name = draft.draft_file.name.split('/')[-1]
                        draft.draft_file.close()

                        submission = DocumentSubmission.objects.create(
                            faculty=request.user,
                            requirement=row['requirement'],
                            status=DocumentSubmission.SubmissionStatus.SUBMITTED,
                        )

                        submission.document_file.save(
                            original_name,
                            file_content,
                            save=True,
                        )

                        completed_submissions.append(submission)

                        draft.draft_file.delete(save=False)
                        draft.delete()

                request.session['recently_submitted_ids'] = [
                    str(submission.id) for submission in completed_submissions
                ]
                request.session.pop('selected_submission_ids', None)

                messages.success(
                    request,
                    'Selected documents submitted successfully.',
                )

                return redirect('faculty_portal:submission_complete')

            except Exception as e:
                print('SUBMISSION ERROR:', repr(e))

                messages.error(
                    request,
                    'An error occurred while processing your submission. Please try again.',
                )

                return redirect('faculty_portal:review_confirm')

    selected_ids = request.session.get('selected_submission_ids', [])

    valid_ids = {str(requirement.id) for requirement in requirements}
    selected_ids = [value for value in selected_ids if value in valid_ids]

    if not selected_ids:
        messages.info(request, 'Please select at least one document to continue.')
        return redirect('faculty_portal:upload_files')

    selected_rows = []

    for requirement in requirements:
        if str(requirement.id) not in selected_ids:
            continue

        draft = drafts_by_requirement.get(requirement.id)

        selected_rows.append({
            'requirement': requirement,
            'draft': draft,
            'is_ready': bool(draft and draft.draft_file),
        })

    all_ready = bool(selected_rows) and all(row['is_ready'] for row in selected_rows)

    context = {
        'rows': selected_rows,
        'all_ready': all_ready,
    }

    return render(
        request,
        'faculty_portal/core/submission_bin/review_confirm.html',
        context,
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

    form = DocumentRevisionForm(
        request.POST,
        request.FILES,
    )

    if not form.is_valid():
        messages.error(
            request,
            'Failed to resubmit. Please check the file format and size.'
        )
        return redirect('faculty_portal:upload_files')

    try:
        with transaction.atomic():
            uploaded_file = form.cleaned_data['file']

            last_version = (
                submission.revisions
                .order_by('-version_number')
                .values_list('version_number', flat=True)
                .first()
            )

            next_version = (last_version or 0) + 1

            DocumentRevision.objects.create(
                submission=submission,
                version_number=next_version,
            )

            old_file_name = submission.document_file.name

            submission.document_file.save(
                uploaded_file.name,
                uploaded_file,
                save=False,
            )

            submission.status = DocumentSubmission.SubmissionStatus.RESUBMITTED
            submission.resubmitted_at = timezone.now()

            submission.save(
                update_fields=[
                    'document_file',
                    'status',
                    'resubmitted_at',
                ]
            )

            new_file_name = submission.document_file.name

            if old_file_name and old_file_name != new_file_name:
                submission.document_file.storage.delete(old_file_name)

        messages.success(request, 'Document resubmitted successfully.')

    except Exception as e:
        print('RESUBMISSION ERROR:', repr(e))
        messages.error(
            request,
            'An error occurred while processing your resubmission. Please try again.'
        )

    return redirect('faculty_portal:upload_files')
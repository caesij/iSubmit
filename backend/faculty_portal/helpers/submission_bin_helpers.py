from django.shortcuts import redirect
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.core.files.base import ContentFile

from submissions.models import (
    Requirement,
    DraftUpload,
    DocumentSubmission,
    DocumentRevision,
)
from submissions.forms import DraftUploadForm

def run_ocr_if_enabled(draft):
    if not getattr(draft.requirement, 'ocr_enabled', False):
        return


def get_available_requirements(user):
    already_submitted_ids = (
        DocumentSubmission.objects
        .filter(faculty=user)
        .exclude(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)
        .values_list('requirement_id', flat=True)
    )

    return (
        Requirement.objects
        .filter(status=Requirement.ReqStatus.ACTIVE)
        .filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            | Q(assigned_to=user.faculty_type)
        )
        .exclude(id__in=already_submitted_ids)
        .order_by('deadline')
    )


def get_drafts_by_requirement(user, requirements):
    drafts = DraftUpload.objects.filter(faculty=user, requirement__in=requirements)
    return {draft.requirement_id: draft for draft in drafts}


def get_needs_revision_by_requirement(user, requirements):
    submissions = (
        DocumentSubmission.objects
        .filter(
            faculty=user,
            requirement__in=requirements,
            status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
        )
        .select_related('requirement')
        .prefetch_related('revisions__reviews')
    )
    return {submission.requirement_id: submission for submission in submissions}


def build_upload_rows(requirements, drafts_by_requirement, needs_revision_by_requirement):
    rows = []

    for requirement in requirements:
        submission = needs_revision_by_requirement.get(requirement.id)

        rows.append({
            'requirement': requirement,
            'draft': drafts_by_requirement.get(requirement.id),
            'submission': submission,
            'needs_revision_submission': submission,
            'is_resubmission': bool(submission),
        })

    return rows


def build_selected_rows(requirements, selected_ids, drafts_by_requirement):
    rows = []

    for requirement in requirements:
        if str(requirement.id) not in selected_ids:
            continue

        draft = drafts_by_requirement.get(requirement.id)

        rows.append({
            'requirement': requirement,
            'draft': draft,
            'is_ready': bool(draft and draft.draft_file),
        })

    return rows


def read_draft_file(draft):
    draft.draft_file.open('rb')
    file_content = ContentFile(draft.draft_file.read())
    original_name = draft.draft_file.name.split('/')[-1]
    draft.draft_file.close()

    return file_content, original_name


def create_submissions(user, selected_rows):
    completed_submissions = []

    with transaction.atomic():
        for row in selected_rows:
            draft = row['draft']
            file_content, original_name = read_draft_file(draft)

            submission = DocumentSubmission.objects.create(
                faculty=user,
                requirement=row['requirement'],
                status=DocumentSubmission.SubmissionStatus.SUBMITTED,
            )
            submission.document_file.save(original_name, file_content, save=True)

            completed_submissions.append(submission)

            draft.draft_file.delete(save=False)
            draft.delete()

    return completed_submissions


def process_submission(request, requirements, drafts_by_requirement):
    selected_ids = request.POST.getlist('selected_requirements')
    valid_ids = {str(requirement.id) for requirement in requirements}
    selected_ids = [value for value in selected_ids if value in valid_ids]

    if not selected_ids:
        messages.error(request, 'Please select at least one document to submit.')
        return redirect('faculty_portal:upload_files')

    selected_rows = build_selected_rows(requirements, selected_ids, drafts_by_requirement)

    if not selected_rows:
        messages.error(request, 'No valid documents were selected.')
        return redirect('faculty_portal:upload_files')

    if any(not row['is_ready'] for row in selected_rows):
        messages.error(request, 'All selected documents must have an attached file.')
        return redirect('faculty_portal:upload_files')

    try:
        completed_submissions = create_submissions(request.user, selected_rows)

        request.session['recently_submitted_ids'] = [
            str(submission.id) for submission in completed_submissions
        ]

        messages.success(request, 'Selected documents submitted successfully.')
        return redirect('faculty_portal:submission_complete')

    except Exception as e:
        print('SUBMISSION ERROR:', repr(e))

        messages.error(
            request,
            'An error occurred while processing your submission. Please try again.',
        )
        return redirect('faculty_portal:upload_files')


def save_draft_form(request, draft, success_message, error_message):
    form = DraftUploadForm(request.POST, request.FILES, instance=draft)

    if form.is_valid():
        draft = form.save()
        run_ocr_if_enabled(draft)
        messages.success(request, success_message)
    else:
        messages.error(request, error_message)

    return redirect('faculty_portal:upload_files')


def get_next_version(submission):
    last_version = (
        submission.revisions
        .order_by('-version_number')
        .values_list('version_number', flat=True)
        .first()
    )

    return (last_version or 0) + 1


def apply_resubmission(submission, uploaded_file):
    DocumentRevision.objects.create(
        submission=submission,
        version_number=get_next_version(submission),
    )

    old_file_name = submission.document_file.name

    submission.document_file.save(uploaded_file.name, uploaded_file, save=False)
    submission.status = DocumentSubmission.SubmissionStatus.RESUBMITTED
    submission.resubmitted_at = timezone.now()
    submission.save(update_fields=['document_file', 'status', 'resubmitted_at'])

    new_file_name = submission.document_file.name

    if old_file_name and old_file_name != new_file_name:
        submission.document_file.storage.delete(old_file_name)
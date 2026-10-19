import logging
import mimetypes
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.files import File
from django.db import transaction
from django.db.models import Max, Q
from django.shortcuts import redirect
from django.utils import timezone

from admin_staff_portal.realtime import refresh_admin_dashboard, refresh_staff_dashboard
from faculty_portal.realtime import refresh_faculty_dashboard, refresh_faculty_submission_bin
from notifications.models import NotificationPreference
from notifications.services import notify_roles
from submissions.forms import DraftUploadForm
from submissions.models import (
    DocumentMetadata,
    DocumentRevision,
    DocumentSubmission,
    DraftUpload,
    Requirement
)

logger = logging.getLogger(__name__)
User = get_user_model()

UPLOAD_PAGE = 'faculty_portal:upload_files'
OCR = DocumentMetadata.OCRStatus
NLP = DocumentMetadata.NLPStatus


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def delete_stored_file(storage, file_name):
    if not storage or not file_name:
        return
    try:
        storage.delete(file_name)
    except Exception:
        logger.exception('Could not delete file %s from storage.', file_name)


def delete_file_after_commit(storage, file_name):
    transaction.on_commit(lambda: delete_stored_file(storage, file_name))


def _is_pdf(filename):
    return Path(filename).suffix.lower() == '.pdf'


def _stored_file_size(draft):
    try:
        return draft.draft_file.storage.size(draft.draft_file.name)
    except Exception:
        logger.exception('Could not read the uploaded file size from storage.')
        return None


# ---------------------------------------------------------------------------
# Document metadata (OCR / NLP state for a draft)
# ---------------------------------------------------------------------------

def _build_metadata_values(draft, uploaded_file=None):
    requirement = draft.requirement

    if uploaded_file is not None:
        filename = Path(uploaded_file.name).name
        content_type = getattr(uploaded_file, 'content_type', '')
        file_size = getattr(uploaded_file, 'size', None)
    else:
        filename = Path(draft.draft_file.name).name
        content_type = mimetypes.guess_type(filename)[0] or ''
        file_size = _stored_file_size(draft)

    if not requirement.ocr_enabled:
        ocr_status, ocr_error = OCR.NOT_REQUIRED, ''
    elif not _is_pdf(filename):
        ocr_status, ocr_error = OCR.FAILED, 'OCR supports PDF files only. Replace this file with a PDF.'
    else:
        ocr_status, ocr_error = OCR.PENDING, ''

    return {
        'faculty_id': draft.faculty_id,
        'requirement_id': draft.requirement_id,
        'draft_id': draft.pk,
        'submission_id': None,
        'version_number': 1,
        'original_filename': filename,
        'storage_file_name': draft.draft_file.name,
        'content_type': content_type or '',
        'file_size': file_size,
        'page_count': None,
        'ocr_status': ocr_status,
        'extracted_text': '',
        'ocr_error': ocr_error,
        'ocr_completed_at': None,
        'nlp_status': NLP.PENDING if requirement.nlp_enabled else NLP.NOT_REQUIRED,
        'nlp_result': {},
        'nlp_error': '',
        'nlp_completed_at': None,
    }


def _needs_full_reset(draft, metadata):
    """True when the metadata no longer describes the draft's current file."""
    if metadata is None or metadata.storage_file_name != draft.draft_file.name:
        return True
    # The requirement started requiring OCR after this file was uploaded.
    return draft.requirement.ocr_enabled and metadata.ocr_status == OCR.NOT_REQUIRED


def _needs_nlp_pending(draft, metadata):
    """The requirement started requiring NLP after this file was uploaded."""
    return draft.requirement.nlp_enabled and metadata.nlp_status == NLP.NOT_REQUIRED


def _metadata_is_current(draft, metadata):
    return not _needs_full_reset(draft, metadata) and not _needs_nlp_pending(draft, metadata)


def _reset_metadata(draft, metadata, uploaded_file):
    values = _build_metadata_values(draft, uploaded_file)

    if metadata is None:
        return DocumentMetadata.objects.create(**values)

    values['ocr_request_id'] = metadata.ocr_request_id + 1
    for field, value in values.items():
        setattr(metadata, field, value)
    metadata.save()
    return metadata


def _mark_nlp_pending(metadata):
    metadata.nlp_status = NLP.PENDING
    metadata.nlp_error = ''
    metadata.nlp_result = {}
    metadata.nlp_completed_at = None
    metadata.save(update_fields=['nlp_status', 'nlp_error', 'nlp_result', 'nlp_completed_at', 'updated_at',])


def ensure_document_metadata(draft, uploaded_file=None, force_reset=False, metadata=None):
    if not draft or not draft.draft_file:
        return None, False

    metadata = metadata or DocumentMetadata.objects.filter(draft=draft).first()

    if force_reset or _needs_full_reset(draft, metadata):
        metadata = _reset_metadata(draft, metadata, uploaded_file)
        return metadata, metadata.ocr_status == OCR.PENDING

    if _needs_nlp_pending(draft, metadata):
        _mark_nlp_pending(metadata)

    return metadata, False


# ---------------------------------------------------------------------------
# OCR scheduling
# ---------------------------------------------------------------------------

def _mark_enqueue_failed(metadata_id, request_id):
    metadata = (
        DocumentMetadata.objects
        .filter(pk=metadata_id, ocr_request_id=request_id, draft__isnull=False)
        .select_related('faculty')
        .first()
    )
    if not metadata:
        return

    metadata.ocr_status = OCR.FAILED
    metadata.ocr_error = (
        'OCR could not be queued. Check that the OCR worker and Redis are running, '
        'then replace the PDF or contact support.'
    )
    metadata.ocr_completed_at = timezone.now()
    metadata.save(update_fields=['ocr_status', 'ocr_error', 'ocr_completed_at', 'updated_at'])

    try:
        refresh_faculty_submission_bin(metadata.faculty)
    except Exception:
        logger.exception('Could not refresh the faculty Submission Bin.')


def _enqueue_ocr(metadata_id, request_id):
    try:
        from submissions.tasks import process_document_ocr
        process_document_ocr.delay(str(metadata_id), str(request_id))
    except Exception:
        logger.exception('Could not queue OCR for metadata record %s.', metadata_id)
        _mark_enqueue_failed(metadata_id, request_id)


def schedule_ocr(metadata):
    if not metadata or metadata.ocr_status != OCR.PENDING:
        return
    metadata_id, request_id = metadata.pk, metadata.ocr_request_id
    transaction.on_commit(lambda: _enqueue_ocr(metadata_id, request_id))


def run_ocr_if_enabled(draft):
    metadata, should_enqueue = ensure_document_metadata(draft)
    if should_enqueue:
        schedule_ocr(metadata)
    return metadata


# ---------------------------------------------------------------------------
# Loading data for the Submission Bin page
# ---------------------------------------------------------------------------


def get_available_requirements(user, requirement_ids=None):
    submitted_ids = (
        DocumentSubmission.objects
        .filter(faculty=user)
        .exclude(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)
        .values_list('requirement_id', flat=True)
    )

    requirements = (
        Requirement.objects
        .filter(status=Requirement.ReqStatus.ACTIVE)
        .filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            | Q(assigned_to=user.faculty_type)
        )
        .exclude(id__in=submitted_ids)
    )

    if requirement_ids is not None:
        requirements = requirements.filter(id__in=requirement_ids)

    return list(requirements.order_by('deadline'))



def _load_drafts_with_metadata(user, requirements):
    drafts = list(
        DraftUpload.objects
        .filter(faculty=user, requirement__in=requirements)
        .select_related('requirement')
    )
    
    metadata_by_draft = {
        m.draft_id: m
        for m in DocumentMetadata.objects.filter(draft_id__in=[d.pk for d in drafts])
    }

    for draft in drafts:
        if not draft.draft_file:
            continue
        metadata = metadata_by_draft.get(draft.pk)
        if _metadata_is_current(draft, metadata):
            continue
        metadata, should_enqueue = ensure_document_metadata(draft, metadata=metadata)
        metadata_by_draft[draft.pk] = metadata
        if should_enqueue:
            schedule_ocr(metadata)

    return {d.requirement_id: d for d in drafts}, metadata_by_draft


def _load_needs_revision(user, requirements, include_history):
    submissions = (
        DocumentSubmission.objects
        .filter(
            faculty=user,
            requirement__in=requirements,
            status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION,
        )
        .select_related('requirement')
    )
    if include_history:
        submissions = submissions.prefetch_related('revisions__reviews')
    return {s.requirement_id: s for s in submissions}


def build_rows(user, requirements, include_history=True):
    drafts, metadata_by_draft = _load_drafts_with_metadata(user, requirements)
    returned = _load_needs_revision(user, requirements, include_history)

    rows = []
    for requirement in requirements:
        draft = drafts.get(requirement.id)
        submission = returned.get(requirement.id)
        rows.append({
            'requirement': requirement,
            'draft': draft,
            'metadata': metadata_by_draft.get(draft.pk) if draft else None,
            'submission': submission,
            'needs_revision_submission': submission,
            'is_resubmission': submission is not None,
            'is_ready': bool(draft and draft.draft_file),
        })
    return rows


def load_upload_rows(user):
    return build_rows(user, get_available_requirements(user), include_history=False)


# ---------------------------------------------------------------------------
# Final submission
# ---------------------------------------------------------------------------

def _submission_block_reason(row):
    requirement = row['requirement']
    metadata = row['metadata']

    if requirement.ocr_enabled:
        if metadata is None:
            return 'OCR metadata is missing. Replace the file to start OCR.'
        if metadata.ocr_status in (OCR.PENDING, OCR.PROCESSING):
            return 'OCR is still processing. Wait for OCR to finish before submitting.'
        if metadata.ocr_status != OCR.COMPLETED:
            return 'OCR did not complete successfully. Replace the PDF and try again.'

    if requirement.nlp_enabled:
        if metadata is None:
            return 'Document validation metadata is missing. Replace the file and try again.'
        if metadata.nlp_status in (NLP.PENDING, NLP.PROCESSING):
            return 'Document validation is still processing. Wait before submitting.'
        if metadata.nlp_status != NLP.PASSED:
            return 'Document validation did not pass. Review the result before submitting.'

    return None


def _original_filename(draft, metadata):
    if metadata and metadata.original_filename:
        return metadata.original_filename
    return Path(draft.draft_file.name).name


def _copy_draft_to_submission(draft, submission, filename, save):
    with draft.draft_file.open('rb') as source:
        submission.document_file.save(filename, File(source), save=save)


def _transfer_metadata_to_submission(draft, submission, metadata=None):
    metadata = metadata or ensure_document_metadata(draft)[0]
    if not metadata:
        return

    latest_version = (
        DocumentMetadata.objects
        .filter(submission=submission)
        .aggregate(max_version=Max('version_number'))['max_version']
        or 0
    )
    metadata.draft = None
    metadata.submission = submission
    metadata.version_number = latest_version + 1
    metadata.storage_file_name = submission.document_file.name
    metadata.save(update_fields=[
        'draft', 'submission', 'version_number', 'storage_file_name', 'updated_at',
    ])


def get_next_version(submission):
    latest = submission.revisions.aggregate(latest=Max('version_number'))['latest']
    return (latest or 0) + 1


def apply_resubmission(submission, draft, original_name, metadata=None):
    DocumentRevision.objects.create(
        submission=submission,
        version_number=get_next_version(submission)
    )

    old_file_name = submission.document_file.name
    old_storage = submission.document_file.storage

    _copy_draft_to_submission(draft, submission, original_name, save=False)
    submission.status = DocumentSubmission.SubmissionStatus.RESUBMITTED
    submission.resubmitted_at = timezone.now()
    submission.save(update_fields=['document_file', 'status', 'resubmitted_at'])

    _transfer_metadata_to_submission(draft, submission, metadata)

    if old_file_name and old_file_name != submission.document_file.name:
        delete_file_after_commit(old_storage, old_file_name)


def create_submissions(user, rows):
    submissions = []

    with transaction.atomic():
        for row in rows:
            draft = row['draft']
            metadata = row['metadata']
            original_name = _original_filename(draft, metadata)

            if row['is_resubmission']:
                submission = row['submission']
                apply_resubmission(submission, draft, original_name, metadata)
            else:
                submission = DocumentSubmission.objects.create(
                    faculty=user,
                    requirement=row['requirement'],
                    status=DocumentSubmission.SubmissionStatus.SUBMITTED,
                )
                _copy_draft_to_submission(draft, submission, original_name, save=True)
                _transfer_metadata_to_submission(draft, submission, metadata)

            submissions.append(submission)

            delete_file_after_commit(draft.draft_file.storage, draft.draft_file.name)
            draft.delete()

    return submissions


def _send_submission_updates(user, submissions):
    try:
        refresh_admin_dashboard()
        refresh_staff_dashboard()
        refresh_faculty_dashboard(user)
        refresh_faculty_submission_bin(user)

        full_name = user.get_full_name()
        for submission in submissions:
            notify_roles(
                roles=[User.Role.ADMIN, User.Role.STAFF],
                notification_type=NotificationPreference.NotificationType.SUBMISSION_NOTIFICATIONS,
                title='New Document Submission',
                message=f'{full_name} submitted {submission.requirement.requirement_title}.',
                link='',
            )
    except Exception:
        logger.exception('Submission realtime/notification update failed.')


def process_submission(request):
    user = request.user
    
    posted_ids = {
        int(value)
        for value in request.POST.getlist('selected_requirements')
        if value.isdecimal()
    }

    requirements = get_available_requirements(user, requirement_ids=posted_ids)

    if not requirements:
        messages.error(request, 'Please select at least one document to submit.')
        return redirect(UPLOAD_PAGE)

    rows = build_rows(user, requirements, include_history=False)

    if not all(row['is_ready'] for row in rows):
        messages.error(request, 'All selected documents must have an attached file.')
        return redirect(UPLOAD_PAGE)

    block_reason = next(filter(None, map(_submission_block_reason, rows)), None)
    if block_reason:
        messages.error(request, block_reason)
        return redirect(UPLOAD_PAGE)

    try:
        submissions = create_submissions(user, rows)
    except Exception:
        logger.exception('Submission failed during final processing.')
        messages.error(request, 'An error occurred while processing your submission. Please try again.')
        return redirect(UPLOAD_PAGE)

    request.session['recently_submitted_ids'] = [str(s.id) for s in submissions]
    transaction.on_commit(lambda: _send_submission_updates(user, submissions))

    messages.success(request, 'Selected documents submitted successfully.')
    return redirect('faculty_portal:submission_complete')


# ---------------------------------------------------------------------------
# Saving an uploaded draft
# ---------------------------------------------------------------------------

def save_draft_form(request, draft, success_message, error_message):
    form = DraftUploadForm(request.POST, request.FILES, instance=draft)
    if not form.is_valid():
        messages.error(request, error_message)
        return redirect(UPLOAD_PAGE)

    uploaded_file = request.FILES.get('draft_file')
    ocr_enabled = draft.requirement.ocr_enabled

    if uploaded_file and ocr_enabled and not _is_pdf(uploaded_file.name):
        messages.error(request, 'This requirement requires OCR, so please upload a PDF file.')
        return redirect(UPLOAD_PAGE)

    old_file_name = draft.draft_file.name if draft.draft_file else ''
    old_storage = draft.draft_file.storage if draft.draft_file else None
    saved_draft = form.save()

    if not uploaded_file:
        metadata, should_enqueue = ensure_document_metadata(saved_draft)
        if should_enqueue:
            schedule_ocr(metadata)
        messages.success(request, success_message)
        return redirect(UPLOAD_PAGE)

    metadata, should_enqueue = ensure_document_metadata(
        saved_draft, uploaded_file=uploaded_file, force_reset=True
    )

    if old_file_name and old_file_name != saved_draft.draft_file.name:
        delete_file_after_commit(old_storage, old_file_name)
    if should_enqueue:
        schedule_ocr(metadata)

    if ocr_enabled:
        success_message += (
            ' OCR status will appear below; final submission will be enabled '
            'after required checks finish.'
        )
    messages.success(request, success_message)
    return redirect(UPLOAD_PAGE)
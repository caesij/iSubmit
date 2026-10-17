import logging
import shutil
import tempfile
from pathlib import Path

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from submissions.models import DocumentMetadata

logger = logging.getLogger(__name__)


def _refresh_faculty_submission_bin(faculty_id):
    try:
        user = get_user_model().objects.filter(pk=faculty_id).first()
        if not user:
            return
        from faculty_portal.realtime import refresh_faculty_submission_bin
        refresh_faculty_submission_bin(user)
    except Exception:
        logger.exception('Could not publish the OCR completion update.')


def _metadata_is_current(metadata, request_id, draft_id, file_name):
    if not (
        metadata
        and metadata.ocr_request_id == request_id
        and metadata.draft_id == draft_id
        and metadata.storage_file_name == file_name
        and metadata.draft_id is not None
    ):
        return False
    try:
        return bool(metadata.draft and metadata.draft.draft_file.name == file_name)
    except Exception:
        return False


@shared_task(bind=True, name='submissions.process_document_ocr', acks_late=True)
def process_document_ocr(self, metadata_id, request_id):
    try:
        request_id = int(request_id)
        if request_id < 1:
            raise ValueError('OCR request ID must be positive.')
    except (TypeError, ValueError, OverflowError):
        logger.warning('Ignoring OCR task with invalid request identifier.')
        return {'status': 'invalid_request'}

    with transaction.atomic():
        metadata = (
            DocumentMetadata.objects
            .select_for_update(of=('self',))
            .select_related('draft', 'requirement')
            .filter(pk=metadata_id)
            .first()
        )
        
        if not metadata:
            return {'status': 'metadata_missing'}
        if metadata.ocr_request_id != request_id:
            return {'status': 'stale_request'}
        if metadata.ocr_status != DocumentMetadata.OCRStatus.PENDING:
            return {'status': 'not_pending'}
        if not metadata.draft_id or not metadata.draft or not metadata.draft.draft_file:
            return {'status': 'draft_missing'}
        if not metadata.requirement.ocr_enabled:
            metadata.ocr_status = DocumentMetadata.OCRStatus.NOT_REQUIRED
            metadata.ocr_error = ''
            metadata.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
            return {'status': 'not_required'}

        draft_id = metadata.draft_id
        file_name = metadata.draft.draft_file.name
        
        if not file_name or metadata.storage_file_name != file_name:
            return {'status': 'stale_file'}
        
        suffix = Path(metadata.original_filename or file_name).suffix.lower()
        
        if suffix != '.pdf':
            metadata.ocr_status = DocumentMetadata.OCRStatus.FAILED
            metadata.ocr_error = 'OCR supports PDF files only. Replace this file with a PDF.'
            metadata.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
            _refresh_faculty_submission_bin(metadata.faculty_id)
            return {'status': 'unsupported_file'}

        faculty_id = metadata.faculty_id
        metadata.ocr_status = DocumentMetadata.OCRStatus.PROCESSING
        metadata.ocr_error = ''
        metadata.ocr_completed_at = None
        metadata.save(update_fields=['ocr_status', 'ocr_error', 'ocr_completed_at', 'updated_at'])

    try:
        draft = metadata.draft
        storage = draft.draft_file.storage
        with tempfile.TemporaryDirectory(prefix='isubmit-ocr-') as temp_dir:
            local_pdf = Path(temp_dir) / 'document.pdf'
            with storage.open(file_name, 'rb') as remote_file:
                with local_pdf.open('wb') as local_file:
                    shutil.copyfileobj(remote_file, local_file)

            from core.ocr import extract_text_and_page_count_from_pdf
            extracted_text, page_count = extract_text_and_page_count_from_pdf(local_pdf)

        with transaction.atomic():
            current = (
                DocumentMetadata.objects
                .select_for_update()
                .filter(pk=metadata_id)
                .first()
            )
            if not _metadata_is_current(current, request_id, draft_id, file_name):
                return {'status': 'stale_result_discarded'}
            if current.ocr_status != DocumentMetadata.OCRStatus.PROCESSING:
                return {'status': 'state_changed'}

            current.ocr_text = extracted_text.strip()
            current.page_count = page_count
            current.ocr_status = DocumentMetadata.OCRStatus.COMPLETED
            current.ocr_error = ''
            current.ocr_completed_at = timezone.now()
            current.save(
                update_fields=[
                    'ocr_text', 'page_count', 'ocr_status', 'ocr_error',
                    'ocr_completed_at', 'updated_at'
                ]
            )

        return {'status': 'completed', 'page_count': page_count}

    except Exception as exc:
        logger.exception('OCR processing failed for metadata record %s.', metadata_id)
        try:
            with transaction.atomic():
                current = (
                    DocumentMetadata.objects
                    .select_for_update()
                    .filter(pk=metadata_id)
                    .first()
                )
                if _metadata_is_current(current, request_id, draft_id, file_name):
                    current.ocr_status = DocumentMetadata.OCRStatus.FAILED
                    
                    current.ocr_error = (
                        f'OCR processing failed ({type(exc).__name__}). '
                        'Please replace the PDF and try again, or contact support.'
                    )
                    
                    current.ocr_completed_at = timezone.now()
                    current.save(update_fields=['ocr_status', 'ocr_error', 'ocr_completed_at', 'updated_at'])
                    
        except Exception:
            logger.exception('Could not save OCR failure state for %s.', metadata_id)
        return {'status': 'failed'}

    finally:
        _refresh_faculty_submission_bin(faculty_id)
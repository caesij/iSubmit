import logging
import shutil
import tempfile
from pathlib import Path

from celery import shared_task
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from core.text_extraction_digi_docs import DocumentTextExtractionError, extract_text
from core.post_correction import correct_lines
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
        logger.exception('Could not publish the document extraction update.')


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


def _known_names():
    names = get_user_model().objects.values_list('first_name', 'last_name')
    return {word for full_name in names for word in ' '.join(full_name).split()}


def _post_correct(lines, scores):
    try:
        return correct_lines(lines, scores, _known_names())
    except Exception:
        logger.exception('Post-correction failed. Saving the plain OCR text.')
        return '\n'.join(lines)


@shared_task(bind=True, name='submissions.process_document_extraction', acks_late=True)
def process_document_extraction(self, metadata_id, request_id):
    try:
        request_id = int(request_id)
        if request_id < 1:
            raise ValueError('Extraction request ID must be positive.')
    except (TypeError, ValueError, OverflowError):
        logger.warning('Ignoring extraction task with invalid request identifier.')
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
        if metadata.requirement.text_processing_mode == metadata.requirement.TextProcessingMode.NONE:
            metadata.ocr_status = DocumentMetadata.OCRStatus.NOT_REQUIRED
            metadata.ocr_error = ''
            metadata.save(update_fields=['ocr_status', 'ocr_error', 'updated_at'])
            return {'status': 'not_required'}
        draft_id = metadata.draft_id
        file_name = metadata.draft.draft_file.name
        
        if not file_name or metadata.storage_file_name != file_name:
            return {'status': 'stale_file'}
        
        suffix = Path(metadata.original_filename or file_name).suffix.lower()
        
        processing_mode = metadata.requirement.text_processing_mode

        if processing_mode == metadata.requirement.TextProcessingMode.OCR and suffix != '.pdf':
            metadata.ocr_status = DocumentMetadata.OCRStatus.FAILED
            metadata.ocr_error = (
                'This requirement requires OCR, so the document must be a PDF.'
            )
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
        with tempfile.TemporaryDirectory(prefix='isubmit-extract-') as temp_dir:
            local_document = Path(temp_dir) / f'document{suffix}'
            with storage.open(file_name, 'rb') as remote_file:
                with local_document.open('wb') as local_file:
                    shutil.copyfileobj(remote_file, local_file)

            if processing_mode == metadata.requirement.TextProcessingMode.OCR:
                from core.ocr import extract_lines_and_page_count_from_pdf
                lines, scores, page_count = (
                    extract_lines_and_page_count_from_pdf(local_document)
                )
                extracted_text = _post_correct(lines, scores)
            else:
                extracted_text, page_count = extract_text(local_document)

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

            current.extracted_text = extracted_text
            current.page_count = page_count
            current.ocr_status = DocumentMetadata.OCRStatus.COMPLETED
            current.ocr_error = ''
            current.ocr_completed_at = timezone.now()
            current.save(
                update_fields=[
                    'extracted_text', 'page_count', 'ocr_status', 'ocr_error',
                    'ocr_completed_at', 'updated_at'
                ]
            )

        return {'status': 'completed', 'page_count': page_count}

    except Exception as exc:
        logger.exception('Document extraction failed for metadata record %s.', metadata_id)
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
                        str(exc)
                        if isinstance(exc, DocumentTextExtractionError)
                        else (
                            'We could not read the text from this document. '
                            'Please replace the file and try again, or contact support.'
                        )
                    )
                    
                    current.ocr_completed_at = timezone.now()
                    current.save(update_fields=['ocr_status', 'ocr_error', 'ocr_completed_at', 'updated_at'])
                    
        except Exception:
            logger.exception('Could not save OCR failure state for %s.', metadata_id)
        return {'status': 'failed'}

    finally:
        _refresh_faculty_submission_bin(faculty_id)
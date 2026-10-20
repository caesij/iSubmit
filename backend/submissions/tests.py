from django.test import TestCase

from submissions.models import DocumentMetadata, Requirement


class DocumentMetadataReadinessTests(TestCase):
    def test_no_text_processing_does_not_require_extraction(self):
        requirement = Requirement(
            text_processing_mode=Requirement.TextProcessingMode.NONE,
            nlp_enabled=False,
        )
        metadata = DocumentMetadata(
            requirement=requirement,
            ocr_status=DocumentMetadata.OCRStatus.NOT_REQUIRED,
        )

        self.assertTrue(metadata.is_ready_for_submission)

    def test_digital_processing_requires_completed_extraction(self):
        requirement = Requirement(
            text_processing_mode=Requirement.TextProcessingMode.DIGITAL,
            nlp_enabled=False,
        )
        metadata = DocumentMetadata(
            requirement=requirement,
            ocr_status=DocumentMetadata.OCRStatus.PENDING,
        )

        self.assertFalse(metadata.is_ready_for_submission)

        metadata.ocr_status = DocumentMetadata.OCRStatus.COMPLETED

        self.assertTrue(metadata.is_ready_for_submission)

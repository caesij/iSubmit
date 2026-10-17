import gc
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
import pymupdf
from paddleocr import PaddleOCR

from core.ocr_preprocessing import preprocess_image

ocr = None


def _get_ocr_engine():
    global ocr
    if ocr is None:
        ocr = PaddleOCR(
            lang='en',
            device='cpu',
            text_detection_model_name='PP-OCRv5_mobile_det',
            text_recognition_model_name='PP-OCRv5_mobile_rec',
            cpu_threads=2,
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_det_limit_side_len=1536,
            text_det_limit_type='max',
        )
    return ocr


def extract_text_and_page_count_from_pdf(pdf_path):
    pdf_path = Path(pdf_path)
    if pdf_path.suffix.lower() != '.pdf':
        raise ValueError('OCR is only supported for PDF files.')

    document = pymupdf.open(pdf_path)
    texts = []
    page_count = len(document)
    engine = _get_ocr_engine()

    with TemporaryDirectory(prefix='isubmit-ocr-pages-') as temp_dir:
        try:
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(
                    dpi=200,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )
                image = np.frombuffer(pixmap.samples, dtype=np.uint8)
                image = image.reshape(pixmap.height, pixmap.width, 3)
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
                processed = preprocess_image(image)

                processed_path = Path(temp_dir) / f'page_{page_number}.png'
                if not cv2.imwrite(str(processed_path), processed):
                    raise RuntimeError(f'Failed to save processed page {page_number}.')

                results = engine.predict(str(processed_path))
                for result in results:
                    data = result.json
                    page_text = data.get('res', {}).get('rec_texts', [])
                    texts.extend(str(text) for text in page_text if text)

                del results, processed, image, pixmap
                gc.collect()
        finally:
            document.close()

    return '\n'.join(texts), page_count


def extract_text_from_pdf(pdf_path):
    text, _page_count = extract_text_and_page_count_from_pdf(pdf_path)
    return text
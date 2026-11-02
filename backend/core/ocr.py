import gc
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
import pymupdf
from paddleocr import PaddleOCR

from core.ocr_preprocessing import preprocess_image

ocr = None


def _layout_lines(texts, polygons):
    entries = []
    for text, polygon in zip(texts, polygons):
        if not text or not polygon:
            continue
        x_values = [point[0] for point in polygon]
        y_values = [point[1] for point in polygon]
        entries.append((min(y_values), min(x_values), max(x_values), text.strip()))

    entries.sort(key=lambda item: (item[0], item[1]))
    lines = []
    for top, left, right, text in entries:
        if not lines or top - lines[-1]['top'] > 24:
            lines.append({'top': top, 'parts': [(left, right, text)]})
        else:
            lines[-1]['parts'].append((left, right, text))

    formatted = []
    for line in lines:
        parts = sorted(line['parts'])
        output = []
        cursor = 0
        for left, right, text in parts:
            gap = max(1, round((left - cursor) / 8)) if output else 0
            output.append(' ' * gap + text)
            cursor = right
        formatted.append(''.join(output).rstrip())
    return formatted


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


def extract_lines_and_page_count_from_pdf(pdf_path):
    pdf_path = Path(pdf_path)
    if pdf_path.suffix.lower() != '.pdf':
        raise ValueError('OCR is only supported for PDF files.')

    document = pymupdf.open(pdf_path)
    lines = []
    scores = []
    page_count = len(document)
    engine = _get_ocr_engine()

    with TemporaryDirectory(prefix='isubmit-ocr-pages-') as temp_dir:
        try:
            for page_number, page in enumerate(document, start=1):
                pixmap = page.get_pixmap(
                    dpi=500,
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
                    data = result.json.get('res', {})
                    page_scores = data.get('rec_scores', [])
                    page_lines = _layout_lines(
                        data.get('rec_texts', []),
                        data.get('rec_polys', data.get('dt_polys', [])),
                    )
                    lines.extend(page_lines)
                    scores.extend(
                        page_scores[index] if index < len(page_scores) else None
                        for index in range(len(page_lines))
                    )

                del results, processed, image, pixmap
                gc.collect()
        finally:
            document.close()

    return lines, scores, page_count


def extract_text_from_pdf(pdf_path):
    lines, _scores, _page_count = extract_lines_and_page_count_from_pdf(pdf_path)
    return '\n'.join(lines)
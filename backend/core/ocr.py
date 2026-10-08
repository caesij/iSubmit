import gc
import cv2
import numpy as np
import pymupdf

from pathlib import Path
from tempfile import TemporaryDirectory

from paddleocr import PaddleOCR

from .ocr_preprocessing import preprocess_image


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


def extract_text_from_pdf(pdf_path):
    pdf_path = Path(pdf_path)

    if pdf_path.suffix.lower() != '.pdf':
        raise ValueError('OCR is only supported for PDF files.')

    document = pymupdf.open(pdf_path)
    texts = []

    with TemporaryDirectory() as temp_dir:
        try:
            for page_number, page in enumerate(document, start=1):
                print(f'Processing page {page_number}...')

                pixmap = page.get_pixmap(
                    dpi=200,
                    colorspace=pymupdf.csRGB,
                    alpha=False,
                )

                image = np.frombuffer(
                    pixmap.samples,
                    dtype=np.uint8
                )

                image = image.reshape(
                    pixmap.height,
                    pixmap.width,
                    3
                )

                image = cv2.cvtColor(
                    image,
                    cv2.COLOR_RGB2BGR
                )

                processed = preprocess_image(image)

                processed_path = (
                    Path(temp_dir) /
                    f'page_{page_number}.png'
                )

                success = cv2.imwrite(
                    str(processed_path),
                    processed
                )

                if not success:
                    raise RuntimeError(
                        f'Failed to save processed page {page_number}.'
                    )

                print(f'Running OCR on page {page_number}...')

                results = ocr.predict(
                    str(processed_path)
                )

                for result in results:
                    data = result.json

                    page_text = data['res'].get(
                        'rec_texts',
                        []
                    )

                    texts.extend(page_text)

                del results
                del processed
                del image
                del pixmap

                gc.collect()

                print(f'Finished page {page_number}.')

        finally:
            document.close()

    return '\n'.join(texts)
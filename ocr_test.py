from backend.core.ocr import extract_text_from_pdf


PDF_PATH = "ocr_samples/ocr_test_complex_form.pdf"

def main():
    print("Starting OCR test...")
    print(f"File: {PDF_PATH}")
    print()

    try:
        text = extract_text_from_pdf(PDF_PATH)

        print("===== EXTRACTED TEXT =====")
        print(text)
        print("==========================")

    except Exception as error:
        print("OCR test failed:")
        print(error)


if __name__ == "__main__":
    main()
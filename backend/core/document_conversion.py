import shutil
import subprocess
from pathlib import Path


class DocumentConversionError(Exception):
    pass


def convert_to_pdf(file_path, output_directory):
    source = Path(file_path)
    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)

    renderer = shutil.which('libreoffice') or shutil.which('soffice')
    if not renderer:
        raise DocumentConversionError(
            'DOCX/XLSX OCR requires LibreOffice to be installed on the extraction worker.'
        )

    try:
        result = subprocess.run(
            [
                renderer,
                '--headless',
                '--convert-to', 'pdf',
                '--outdir', str(output_directory),
                str(source),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise DocumentConversionError(
            'The document could not be converted to PDF for OCR.'
        ) from exc

    converted_file = output_directory / f'{source.stem}.pdf'
    if result.returncode != 0 or not converted_file.is_file():
        detail = (result.stderr or result.stdout).strip()
        message = 'The document could not be converted to PDF for OCR.'
        if detail:
            message = f'{message} {detail}'
        raise DocumentConversionError(message)

    return converted_file

from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree


class DocumentTextExtractionError(Exception):
    pass


def extract_text(file_path):
    suffix = Path(file_path).suffix.lower()

    if suffix == '.pdf':
        return _extract_pdf(file_path)
    if suffix == '.docx':
        return _extract_docx(file_path)
    if suffix == '.xlsx':
        return _extract_xlsx(file_path)

    raise DocumentTextExtractionError('This file type does not support direct text extraction.')


def _extract_pdf(file_path):
    import fitz

    with fitz.open(file_path) as document:
        text = '\n'.join(page.get_text('text') for page in document).strip()
        if not text:
            raise DocumentTextExtractionError('No embedded text was found. Enable OCR for scanned documents.')
        return text, len(document)


def _extract_docx(file_path):
    namespace = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

    with ZipFile(file_path) as archive:
        try:
            document = ElementTree.fromstring(
                archive.read('word/document.xml')
            )
        except KeyError as exc:
            raise DocumentTextExtractionError(
                'The DOCX document is missing its main document content.'
            ) from exc

    lines = []
    for paragraph in document.iter(f'{namespace}p'):
        line = ''.join(
            node.text or ''
            for node in paragraph.iter(f'{namespace}t')
        ).strip()
        if line:
            lines.append(line)

    if not lines:
        raise DocumentTextExtractionError('No text was found in the DOCX document.')

    return '\n'.join(lines), None


def _extract_xlsx(file_path):
    namespace = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'

    with ZipFile(file_path) as archive:
        shared_strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ElementTree.fromstring(archive.read('xl/sharedStrings.xml'))
            for item in root.findall(f'{namespace}si'):
                shared_strings.append(''.join(node.text or '' for node in item.iter(f'{namespace}t')))

        lines = []
        for name in archive.namelist():
            if not name.startswith('xl/worksheets/sheet') or not name.endswith('.xml'):
                continue
            root = ElementTree.fromstring(archive.read(name))
            for row in root.findall(f'.//{namespace}row'):
                values = []
                for cell in row.findall(f'{namespace}c'):
                    if cell.get('t') == 'inlineStr':
                        inline_text = ''.join(
                            node.text or ''
                            for node in cell.iter(f'{namespace}t')
                        ).strip()
                        if inline_text:
                            values.append(inline_text)
                        continue
                    value = cell.find(f'{namespace}v')
                    if value is None or value.text is None:
                        continue
                    cell_value = value.text
                    if cell.get('t') == 's':
                        cell_value = shared_strings[int(cell_value)]
                    values.append(cell_value)
                if values:
                    lines.append(' | '.join(values))

    if not lines:
        raise DocumentTextExtractionError('No text was found in the XLSX workbook.')

    return '\n'.join(lines), None

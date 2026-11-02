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
        lines = []
        for page in document:
            entries = []
            for block in page.get_text('dict').get('blocks', []):
                for block_line in block.get('lines', []):
                    spans = block_line.get('spans', [])
                    if not spans:
                        continue
                    text = ''.join(span.get('text', '') for span in spans).strip()
                    if text:
                        x0, y0, _x1, _y1 = block_line['bbox']
                        entries.append((round(y0, 1), x0, text))

            entries.sort(key=lambda entry: (entry[0], entry[1]))
            grouped = []
            for top, left, text in entries:
                if not grouped or top - grouped[-1][0] > 4:
                    grouped.append([top, [(left, text)]])
                else:
                    grouped[-1][1].append((left, text))

            for _top, parts in grouped:
                parts.sort()
                line = []
                cursor = 0
                for left, text in parts:
                    gap = max(1, round((left - cursor) / 5)) if line else 0
                    line.append(' ' * gap + text)
                    cursor = left + len(text) * 5
                lines.append(''.join(line).rstrip())

        text = '\n'.join(lines).strip()
        if not text:
            raise DocumentTextExtractionError(
                'We could not find selectable text in this PDF. '
                'Please upload a digital PDF or ask an administrator to enable OCR.'
            )
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
        raise DocumentTextExtractionError(
            'We could not find readable text in this Word document.'
        )

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
        raise DocumentTextExtractionError(
            'We could not find readable text in this spreadsheet.'
        )

    return '\n'.join(lines), None

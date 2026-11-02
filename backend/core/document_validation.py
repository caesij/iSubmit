import re
from functools import lru_cache


class DocumentValidationError(Exception):
    pass


_INSTRUCTION_RE = re.compile(
    r'^\s*(?P<field>[A-Za-z][A-Za-z0-9 /&()_-]*?)\s*:\s*required\s*$',
    re.IGNORECASE,
)
_LABEL_RE = re.compile(
    r'^\s*(?P<label>[A-Za-z][A-Za-z0-9 /&()_-]*?)\s*[:\u2013-]\s*(?P<value>.*?)\s*$'
)
_LABEL_ONLY_RE = re.compile(
    r'^\s*(?P<label>[A-Za-z][A-Za-z0-9 /&()_-]*?)\s*:\s*$'
)
_INLINE_LABEL_RE = re.compile(
    r'\s+[A-Z][A-Za-z0-9_-]{0,30}\s*:',
    re.IGNORECASE,
)
_DESCRIPTIVE_FIELD_WORDS = {
    'name', 'title', 'code', 'number', 'email', 'address', 'value',
}
_OCR_SEPARATOR_RE = re.compile(r'^[\W_]*')
_HEADER_RE = re.compile(
    r'\b[A-Z][A-Z0-9/&-]{2,}\b'
)


def _normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def parse_validation_instructions(instructions):
    fields = []
    errors = []
    seen = set()
    for line_number, line in enumerate((instructions or '').splitlines(), 1):
        if not line.strip():
            continue
        match = _INSTRUCTION_RE.match(line)
        if not match:
            errors.append(f'Line {line_number} must use: Field name: required.')
            continue
        name = ' '.join(match.group('field').split()).strip()
        key = _normalize(name)
        if key in seen:
            errors.append(f'Line {line_number} repeats the field "{name}".')
            continue
        seen.add(key)
        fields.append({'name': name, 'key': key, 'mode': 'required'})
    return fields, errors


@lru_cache(maxsize=1)
def _load_model():
    try:
        import spacy
        return spacy.load('en_core_web_sm', disable=['parser', 'lemmatizer'])
    except (ImportError, OSError) as exc:
        raise DocumentValidationError(
            'The NLP validation model is not available.'
        ) from exc


def _clean_value(value):
    return re.sub(r'\s+', ' ', value).strip(' \t:;,.-')


def _label_pattern(field_name, drop_descriptive=False, anchored=True):
    tokens = field_name.split()
    if drop_descriptive:
        tokens = [
            token for token in tokens
            if _normalize(token) not in _DESCRIPTIVE_FIELD_WORDS
        ] or tokens
    escaped = [re.escape(token) for token in tokens]
    prefix = r'^\s*[\W_]*' if anchored else r'(?<![A-Za-z0-9])'
    return re.compile(
        rf'{prefix}{"\\s+".join(escaped)}(?=\s|[:\u2013\-]|$)',
        re.IGNORECASE,
    )


def _field_patterns(field_name):
    full = _label_pattern(field_name, anchored=False)
    fallback = _label_pattern(
        field_name,
        drop_descriptive=True,
        anchored=False,
    )
    return (full,) if full.pattern == fallback.pattern else (full, fallback)


def _inline_field_patterns(field_names):
    return [
        _label_pattern(name, drop_descriptive=drop, anchored=False)
        for name in field_names
        for drop in (False, True)
        if not (drop and _label_pattern(name).pattern == _label_pattern(
            name, drop_descriptive=True
        ).pattern)
    ]


def _value_after_label(line, label_match, known_labels):
    remainder = line[label_match.end():].lstrip(' \t:\u2013-')
    remainder = _OCR_SEPARATOR_RE.sub('', remainder).strip()
    if not remainder:
        return ''
    next_label_positions = [
        match.start()
        for pattern in (*known_labels, _INLINE_LABEL_RE)
        for match in pattern.finditer(remainder)
        if match.start() >= 0
    ]
    if next_label_positions:
        remainder = remainder[:min(next_label_positions)]
    if _looks_like_header(remainder, known_labels):
        return ''
    return _clean_value(remainder)


def _looks_like_header(value, known_labels):
    normalized = _normalize(value)
    if not normalized or len(value) > 48:
        return False
    if any(pattern.fullmatch(value.strip()) for pattern in known_labels):
        return True
    return (
        value.strip().isupper()
        and not any(character.isdigit() for character in value)
        and len(normalized.split()) <= 4
    )


def _aligned_value(line, match, next_line, known_labels):
    next_positions = [
        candidate.start()
        for candidate in _HEADER_RE.finditer(line)
        if candidate.start() >= match.end()
    ] + [
        candidate.start()
        for pattern in known_labels
        for candidate in pattern.finditer(line)
        if candidate.start() >= match.end()
    ]
    end = min(next_positions) if next_positions else len(next_line)
    start = min(match.start(), len(next_line))
    end = min(end, len(next_line))
    value = _clean_value(next_line[start:end])
    return '' if _looks_like_header(value, known_labels) else value


def _find_label_value(field_name, lines, all_fields):
    patterns = _field_patterns(field_name)
    known_patterns = _inline_field_patterns(all_fields)
    for pattern in patterns:
        for index, line in enumerate(lines):
            match = pattern.search(line)
            if not match:
                continue
            value = _value_after_label(line, match, known_patterns)
            if value:
                return value, index
            if index + 1 < len(lines):
                next_line = lines[index + 1]
                value = _aligned_value(line, match, next_line, known_patterns)
                if value:
                    return value, index + 1
                if not any(other.search(next_line) for other in known_patterns):
                    value = _clean_value(next_line)
                    if value:
                        return value, index + 1
    return '', None


def _find_label_candidates(field_name, lines, all_fields):
    patterns = _field_patterns(field_name)
    known_patterns = _inline_field_patterns(all_fields)
    matches = [
        (index, pattern.search(line))
        for pattern in patterns[:1]
        for index, line in enumerate(lines)
        if pattern.search(line)
    ]
    if not matches:
        matches = [
            (index, pattern.search(line))
            for pattern in patterns[1:]
            for index, line in enumerate(lines)
            if pattern.search(line)
        ]
    candidates = []
    seen = set()
    for index, match in matches:
        line = lines[index]
        value = _value_after_label(line, match, known_patterns)
        source = 'label_linked'
        candidate_line = index
        if not value and index + 1 < len(lines):
            value = _aligned_value(line, match, lines[index + 1], known_patterns)
            source = 'aligned_column'
            candidate_line = index + 1
            if value and not re.search(r'\s{2,}|\t', line):
                value = _clean_value(lines[index + 1])
                source = 'adjacent_line'
        if not value and index + 1 < len(lines):
            next_line = lines[index + 1]
            if not any(other.search(next_line) for other in known_patterns):
                value = _clean_value(next_line)
                source = 'wrapped_line'
                candidate_line = index + 1
        value = _clean_value(value)
        if not value or value in seen:
            continue
        seen.add(value)
        confidence = (
            0.9 if source == 'label_linked'
            else 0.65 if source == 'adjacent_line'
            else 0.85
        )
        if _looks_like_header(value, known_patterns):
            confidence = 0.2
        candidates.append({
            'text': value,
            'confidence': confidence,
            'source': source,
            'line': candidate_line + 1,
            'reliable': confidence >= 0.8,
        })
    return candidates


def _ner_supports_value(doc, value):
    normalized = _normalize(value)
    return any(
        _normalize(entity.text) in normalized or normalized in _normalize(entity.text)
        for entity in doc.ents
    )


def _candidate_confidence(source, value, ner_supported):
    score = {
        'label_linked': 0.82,
        'aligned_column': 0.72,
        'wrapped_line': 0.68,
        'adjacent_line': 0.58,
    }.get(source, 0.5)
    if len(value.split()) >= 2:
        score += 0.04
    if any(character.isdigit() for character in value):
        score -= 0.03
    if ner_supported:
        score += 0.06
    return round(max(0.0, min(score, 0.97)), 2)


def validate_document_text(text, instructions):
    if not text.strip():
        raise DocumentValidationError('No extracted text is available for validation.')

    fields, instruction_errors = parse_validation_instructions(instructions)
    if instruction_errors:
        return _instruction_review(instruction_errors)
    if not fields:
        return _instruction_review([
            'Add at least one field using: Field name: required.'
        ])

    lines = tuple(line.rstrip() for line in text.splitlines() if line.strip())
    doc = _load_model()(text)
    field_names = [field['name'] for field in fields]
    results = {}
    for field in fields:
        candidates = _find_label_candidates(field['name'], lines, field_names)
        for candidate in candidates:
            candidate['confidence'] = _candidate_confidence(
                candidate['source'],
                candidate['text'],
                _ner_supports_value(doc, candidate['text']),
            )
            candidate['reliable'] = candidate['confidence'] >= 0.8
        reliable_candidates = [
            candidate for candidate in candidates if candidate['reliable']
        ]
        results[field['name']] = {
            'mode': 'required',
            'required': True,
            'found': bool(reliable_candidates),
            'values': [candidate['text'] for candidate in reliable_candidates],
            'candidates': candidates,
        }

    missing = [name for name, result in results.items() if not result['found']]
    uncertain = [
        name for name, result in results.items()
        if not result['found'] and result['candidates']
    ]
    recheck = [
        {
            'field': name,
            'reason': (
                'Required field was not found near its label.'
                if name in missing
                else 'A value was found, but NLP could not confirm the candidate.'
            ),
        }
        for name in (*missing, *uncertain)
    ]
    return {
        'status': 'REVIEW' if missing or uncertain else 'PASSED',
        'fields': results,
        'missing_fields': missing,
        'uncertain_fields': uncertain,
        'recheck': recheck,
        'unrecognized_instructions': [],
    }


def _instruction_review(errors):
    return {
        'status': 'REVIEW',
        'fields': {},
        'missing_fields': [],
        'uncertain_fields': [],
        'recheck': [
            {'field': 'validation_instructions', 'reason': error}
            for error in errors
        ],
        'unrecognized_instructions': errors,
    }

import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache


class DocumentValidationError(Exception):
    pass


FOUND_AT = 0.75
UNCERTAIN_AT = 0.45
AMBIGUITY_GAP = 0.05
MAX_CANDIDATES = 5
MAX_SCORED_CANDIDATES = 30

_INSTRUCTION_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z][A-Za-z0-9 /&()_#'\u2019-]*?)\s*:\s*"
    r'(?P<mode>required|optional)\.?\s*$',
    re.IGNORECASE,
)
_WORD_RE = re.compile(r"[A-Za-z0-9#]+(?:['\u2019][A-Za-z]+)?")
_MONTH = (
    r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|'
    r'july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
)
_ORDINAL = r'(?:1st|2nd|3rd|[4-9]th|first|second|third|fourth|fifth|sixth)'

_SEPARATOR_RE = re.compile(r'\.?\s*[:\u2013\u2014-]\s*')
_LEAD_JUNK_RE = re.compile(r'(?i:(?:[\s:;|._=~\u2013\u2014-]|\b(?:is|are|was|were)\b)+)')
_INLINE_LABEL_RE = re.compile(r'\s+[A-Z][A-Za-z0-9_-]{0,30}\s*:', re.IGNORECASE)
_LABEL_LIKE_RE = re.compile(r'^\s*[A-Za-z][A-Za-z0-9 /&()#_-]{0,40}\s*:(?:\s|$)')
_COLUMN_LABEL_RE = re.compile(r'(?:\s{2,}|\t)[A-Za-z][A-Za-z0-9 /&.()#-]{0,40}\s*:(?=\s|$)')
_CHECKED_BOX = r'(?:\[\s*[xX\u2713\u2714/]\s*\]|\(\s*[xX\u2713\u2714/]\s*\)|[\u2611\u2612\u2713\u2714])'
_EMPTY_BOX = r'(?:\[\s*_?\s*\]|\(\s*_?\s*\)|\u2610)'
_BOX_RE = re.compile(rf'({_CHECKED_BOX}|{_EMPTY_BOX})\s*([^\[\(\u2610-\u2612\u2713\u2714]*)')
_CHECKED_BOX_RE = re.compile(_CHECKED_BOX)
_PLACEHOLDER_RE = re.compile(r'^(?:[\W_]*|n/?a|none|nil|null|tbd|blank)$', re.IGNORECASE)

_DESCRIPTIVE_WORDS = {
    'name', 'title', 'code', 'number', 'email', 'address', 'value',
    'no', 'num', 'percent', 'percentage',
}
_QUALIFIER_WORDS = {
    'father', 'mother', 'guardian', 'parent', 'spouse', 'emergency',
    'permanent', 'present', 'current', 'previous', 'mailing', 'billing',
    'shipping', 'home', 'office', 'business', 'work', 'alternate',
    'secondary', 'former', 'other',
}
_ROLE_WORDS = {
    'dean', 'registrar', 'adviser', 'advisor', 'chairperson', 'chair',
    'president', 'director', 'head', 'principal', 'coordinator', 'professor',
    'instructor', 'panelist', 'supervisor', 'treasurer', 'secretary',
    'mentor', 'signatory', 'librarian', 'chancellor', 'vice',
}

_TYPE_WORDS = {
    'email': {'email', 'mail'},
    'phone': {'phone', 'telephone', 'tel', 'mobile', 'cell', 'cellphone', 'fax'},
    'url': {'url', 'website', 'link', 'web'},
    'date': {
        'date', 'dated', 'dob', 'birthday', 'birthdate', 'deadline', 'expiry', 'expiration',
        'graduated', 'enrolled', 'admitted',
    },
    'money': {
        'amount', 'total', 'price', 'cost', 'fee', 'balance', 'subtotal', 'salary', 'charge',
        'rent', 'wage', 'income', 'tax', 'due', 'tuition',
    },
    'percent': {'percent', 'percentage'},
    'quantity': {
        'quantity', 'qty', 'count', 'age', 'weight', 'height', 'length', 'volume', 'unit',
        'credit', 'hour',
    },
    'id': {'number', 'no', 'num', 'id', 'code', 'ref', 'reference', 'serial', 'identifier', 'lrn', '#'},
    'address': {'address', 'street'},
    'location': {
        'city', 'country', 'state', 'province', 'region', 'location', 'place', 'town',
        'municipality', 'barangay', 'district', 'venue',
    },
    'person': {
        'person', 'employee', 'author', 'patient', 'applicant', 'signatory', 'representative',
        'tenant', 'landlord', 'owner', 'manager', 'supervisor', 'witness', 'guardian',
        'beneficiary', 'assignee', 'student', 'adviser', 'advisor', 'mentor', 'instructor',
        'professor', 'teacher', 'lecturer', 'dean', 'registrar', 'chairperson', 'chair',
        'president', 'director', 'coordinator', 'principal', 'head', 'examinee', 'candidate',
        'graduate', 'awardee', 'parent', 'mother', 'father', 'panelist', 'secretary',
        'treasurer', 'officer', 'librarian', 'chancellor',
    },
    'org': {
        'company', 'organization', 'organisation', 'vendor', 'supplier', 'employer', 'agency',
        'institution', 'bank', 'firm', 'business', 'department', 'university', 'school',
        'hospital', 'merchant', 'college', 'faculty', 'institute', 'campus',
    },
    'name': {
        'name', 'customer', 'client', 'payee', 'payer', 'sender', 'party', 'buyer', 'seller',
        'recipient',
    },
    'text': {
        'description', 'note', 'remark', 'comment', 'summary', 'subject', 'title', 'purpose',
        'detail', 'reason', 'memo', 'scope',
    },
    'year': {'year'},
    'term': {'semester', 'sem', 'trimester', 'quarter', 'term'},
    'year_level': {'level', 'standing'},
    'grade': {'gpa', 'gwa', 'cgpa', 'grade', 'mark', 'score', 'rating', 'average'},
    'program': {
        'program', 'programme', 'course', 'degree', 'major', 'curriculum', 'track', 'strand',
        'specialization', 'concentration',
    },
}

_PHRASE_TYPES = {
    ('course', 'code'): 'course_code', ('subject', 'code'): 'course_code',
    ('course', 'number'): 'course_code', ('subject', 'number'): 'course_code',
    ('student', 'number'): 'id', ('student', 'no'): 'id', ('student', 'id'): 'id',
    ('receipt', 'number'): 'id', ('official', 'receipt', 'number'): 'id',
    ('school', 'year'): 'year', ('academic', 'year'): 'year',
    ('graduation', 'year'): 'year', ('year', 'graduated'): 'year',
    ('year', 'of', 'graduation'): 'year',
    ('year', 'level'): 'year_level', ('grade', 'level'): 'year_level',
    ('class', 'standing'): 'year_level', ('place', 'of', 'birth'): 'location',
    ('birth', 'place'): 'location', ('birthplace',): 'location',
    ('date', 'of', 'birth'): 'date',
    ('date', 'of', 'graduation'): 'date', ('graduation', 'date'): 'date',
    ('course', 'title'): 'text', ('subject', 'title'): 'text',
    ('thesis', 'title'): 'text', ('course', 'description'): 'text',
    ('civil', 'status'): 'text', ('marital', 'status'): 'text',
    ('course', 'name'): 'program', ('program', 'name'): 'program',
    ('degree', 'program'): 'program', ('contact', 'person'): 'person',
    ('contact', 'number'): 'phone', ('contact', 'no'): 'phone',
    ('mobile', 'number'): 'phone', ('phone', 'number'): 'phone',
    ('telephone', 'number'): 'phone', ('school', 'attended'): 'org',
    ('school', 'name'): 'org', ('university', 'name'): 'org',
    ('college', 'name'): 'org', ('department', 'name'): 'org',
    ('general', 'weighted', 'average'): 'grade',
    ('grade', 'point', 'average'): 'grade', ('cumulative', 'average'): 'grade',
}

_SYNONYM_GROUPS = [
    ('customer', 'client', 'buyer', 'purchaser', 'bill to', 'sold to', 'account holder'),
    ('vendor', 'supplier', 'seller', 'merchant', 'payee', 'issuer'),
    ('company', 'organization', 'organisation', 'firm', 'business', 'employer'),
    ('date', 'dated'), ('amount', 'total', 'sum', 'balance'),
    ('phone', 'telephone', 'tel', 'mobile', 'cell', 'cellphone', 'contact number', 'contact no'),
    ('email', 'e mail', 'mail', 'email address'), ('address', 'residence'),
    ('number', 'no', 'num', 'id', 'ref', 'reference', '#'),
    ('name', 'full name'), ('invoice', 'bill'),
    ('birth date', 'date of birth', 'dob', 'birthdate', 'birthday'),
    ('zip', 'postal code', 'postcode', 'zip code'),
    ('student', 'pupil', 'learner', 'examinee', 'applicant', 'enrollee'),
    (
        'student number', 'student id', 'student no', 'school id', 'id number', 'id no',
        'matriculation number', 'matric number', 'learner reference number', 'lrn',
    ),
    ('receipt number', 'receipt no', 'official receipt number', 'or number', 'o r no', 'o r number'),
    ('student name', 'received from', 'paid by', 'name of payer'),
    ('school year', 'academic year', 'ay', 'sy', 'a y', 's y'),
    ('semester', 'sem', 'term'),
    ('course', 'program', 'programme', 'degree', 'curriculum'),
    ('major', 'specialization', 'concentration', 'field of study'),
    ('college', 'faculty', 'department'),
    ('university', 'institution', 'school attended', 'school name', 'alma mater'),
    ('gwa', 'gpa', 'cgpa', 'general weighted average', 'grade point average', 'cumulative average'),
    ('unit', 'credit', 'credit unit'), ('adviser', 'advisor', 'mentor'),
    ('instructor', 'professor', 'teacher', 'lecturer'), ('sex', 'gender'),
    ('nationality', 'citizenship'), ('civil status', 'marital status'),
    ('year level', 'yr level', 'class standing'),
    (
        'thesis title', 'research title', 'dissertation title', 'capstone title',
        'project title', 'title of thesis',
    ),
    ('date of graduation', 'graduation date', 'date graduated', 'graduated on'),
    ('registrar', 'university registrar'), ('dean', 'college dean'),
    ('place of birth', 'birthplace'),
]

_ENTITY_LABELS = {
    'person': {'PERSON'}, 'org': {'ORG'}, 'name': {'PERSON', 'ORG'},
    'location': {'GPE', 'LOC', 'FAC'}, 'address': {'GPE', 'LOC', 'FAC'},
    'date': {'DATE', 'TIME'}, 'money': {'MONEY'}, 'percent': {'PERCENT'},
    'quantity': {'QUANTITY', 'CARDINAL'},
}


def _normalize(value):
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def _clean_token(value):
    token = value.casefold()
    token = re.sub(r"['\u2019]s$", '', token)
    token = token.replace("'", '').replace('\u2019', '')
    return token[:-1] if len(token) > 3 and token.endswith('s') and not token.endswith('ss') else token


def _tokens(value):
    return tuple(_clean_token(match.group()) for match in _WORD_RE.finditer(value))


def _words(line):
    return [
        (_clean_token(match.group()), match.start(), match.end())
        for match in _WORD_RE.finditer(line)
    ]


_WORD_TO_TYPE = {
    _clean_token(word): field_type
    for field_type, words in _TYPE_WORDS.items()
    for word in words
}
_DESCRIPTIVE = {_clean_token(word) for word in _DESCRIPTIVE_WORDS}
_PHRASES = {
    tuple(_tokens(' '.join(words))): field_type for words, field_type in _PHRASE_TYPES.items()
}


def parse_validation_instructions(instructions):
    fields, errors, seen = [], [], set()

    for line_number, line in enumerate((instructions or '').splitlines(), 1):
        if not line.strip():
            continue

        match = _INSTRUCTION_RE.match(line)

        if not match:
            errors.append(f'Line {line_number} must use: Field name: required or optional.')
            continue

        name = ' '.join(match.group('field').split())
        key = _normalize(name)

        if key in seen:
            errors.append(f'Line {line_number} repeats the field "{name}".')
            continue

        seen.add(key)
        fields.append({'name': name, 'key': key, 'mode': match.group('mode').lower()})

    return fields, errors


@lru_cache(maxsize=1)
def _load_model():
    try:
        import spacy
        # The parser is required for sentence and dependency-based fallback.
        return spacy.load('en_core_web_sm', disable=['lemmatizer'])
    except (ImportError, OSError) as exc:
        raise DocumentValidationError('The NLP validation model is not available.') from exc


@dataclass
class _Hit:
    start: int
    end: int
    quality: float
    kind: str
    qualified: bool = False


def _infer_type(tokens):
    for size in range(min(4, len(tokens)), 0, -1):
        for index in range(len(tokens) - size, -1, -1):
            field_type = _PHRASES.get(tuple(tokens[index:index + size]))

            if field_type:
                return field_type

    types = [_WORD_TO_TYPE.get(token) for token in tokens]
    head = types[-1]
    mapped = [field_type for field_type in types if field_type]

    if not mapped:
        return 'text'

    if head is None:
        return mapped[-1] if mapped[-1] != 'money' else 'text'

    earlier = [field_type for field_type in types[:-1] if field_type]
    related = {
        'id': {'phone', 'email', 'url', 'date'},
        'name': {'person', 'org', 'location'},
        'address': {'email', 'url'},
    }.get(head, set())

    return next((field_type for field_type in earlier if field_type in related), head)


def _label_variants(tokens):
    variants = {tuple(tokens): (1.0, 'exact')}

    for group in _SYNONYM_GROUPS:
        members = [_tokens(member) for member in group]

        for member in members:
            size = len(member)

            for index in range(len(tokens) - size + 1):
                if tuple(tokens[index:index + size]) != member:
                    continue

                for other in members:
                    if other != member:
                        replaced = tuple(tokens[:index]) + other + tuple(tokens[index + size:])
                        variants.setdefault(replaced, (0.88, 'alias'))

    for words, (quality, kind) in list(variants.items()):
        shortened = tuple(token for token in words if token not in _DESCRIPTIVE)

        if shortened and len(shortened) < len(words):
            variants.setdefault(shortened, (0.75 if kind == 'exact' else 0.7, 'partial'))

    if len(tokens) == 2:
        variants.setdefault((tokens[1], 'of', tokens[0]), (0.85, 'alias'))

    if len(tokens) == 3 and tokens[1] == 'of':
        variants.setdefault((tokens[2], tokens[0]), (0.85, 'alias'))

    if len(tokens) > 1:
        variants.setdefault((tokens[-1],), (0.5, 'head'))

    return variants


def _build_spec(field):
    tokens = _tokens(field['name'])
    composite = re.search(r'[&/]|\band\b', field['name'], re.IGNORECASE) is not None
    field_type = 'text' if composite else _infer_type(tokens)

    return {
        **field,
        'tokens': tokens,
        'type': field_type,
        'role': field_type in ('person', 'name') and bool(set(tokens) & _ROLE_WORDS),
        'variants': _label_variants(tokens),
    }


# Value patterns are compiled once and reused for every document.
_ID_RE = re.compile(r'(?<![A-Za-z0-9])(?=[A-Za-z0-9/_.-]*\d)[A-Za-z0-9][A-Za-z0-9/_.-]{1,39}(?![A-Za-z0-9])')
_NAME_PART = r"[A-Z][\w'\u2019.-]*"
_NAME_SHAPE_RE = re.compile(
    rf'^(?:(?:Mr|Mrs|Ms|Miss|Dr|Engr|Atty|Prof|Sir|Hon|Rev)\.?\s+)?{_NAME_PART}'
    rf'(?:\s+(?:y|de|del|dela|delos|da|van|von|bin|al|ng|{_NAME_PART})){{1,5}}'
    rf'(?:,?\s+(?:Jr|Sr|II|III|IV|V|Ph\.?D|MD|CPA|RN|LPT|DBA|MBA)\.?)*$'
)
_NAME_COMMA_RE = re.compile(
    rf'^{_NAME_PART}(?:\s+(?:y|de|del|dela|delos|da|van|von|{_NAME_PART})){{0,3}},\s*'
    rf'{_NAME_PART}(?:\s+{_NAME_PART})*(?:\s+(?:Jr|Sr|II|III)\.?)?$'
)
_ORG_SUFFIX_RE = re.compile(
    r'\b(?:inc|corp|corporation|co|company|llc|ltd|limited|plc|gmbh|bank|university|college|'
    r'foundation|association|group|holdings|enterprises|trading|services|partners|industries|'
    r'laboratories|labs|institute|academy|polytechnic|seminary|school|department|faculty|campus)\b\.?',
    re.IGNORECASE,
)
_PROGRAM_WORDS_RE = re.compile(
    r'\b(?:science|arts|engineering|education|technology|business|administration|nursing|'
    r'accountancy|accounting|medicine|pharmacy|architecture|management|studies|computing|'
    r'informatics|biology|chemistry|physics|mathematics|psychology|economics|law|criminology|'
    r'tourism|hospitality|communication|agriculture|forestry|fisheries|information|computer|'
    r'software|networking|marketing|finance|nutrition|dentistry|literature|history|sociology|'
    r'philosophy|journalism|entrepreneurship|secondary|elementary|civil|electrical|mechanical|'
    r'chemical|electronics|industrial|multimedia|animation|stem|humss|abm|tvl)\b',
    re.IGNORECASE,
)
_CAPS_PHRASE_RE = re.compile(r"^[A-Z][\w'\u2019.&-]*(?:[\s,]+[A-Z][\w'\u2019.&-]*){0,5}$")
_PROGRAM_TAIL = (
    r"[A-Za-z][A-Za-z&/'-]*(?:\s+(?!conferred\b|graduated\b|dated\b|effective\b|under\b)"
    r"[A-Za-z][A-Za-z&/'-]*){0,7}"
)

_PATTERNS = {
    'email': [(re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'), 1.0)],
    'url': [(re.compile(r'(?:https?://|www\.)[^\s,;]+', re.I), 1.0)],
    'phone': [(re.compile(r'(?<![\w])\+?\(?\d[\d\s().-]{5,}\d(?![\w])'), 1.0)],
    'date': [
        (re.compile(r'\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b'), 1.0),
        (re.compile(r'\b\d{4}[/.-]\d{1,2}[/.-]\d{1,2}\b'), 1.0),
        (re.compile(rf'\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}\b\.?,?\s*\d{{2,4}}\b', re.I), 1.0),
        (re.compile(rf'\b{_MONTH}\b\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{2,4}}\b', re.I), 1.0),
        (re.compile(rf'\b{_MONTH}\b\.?,?\s+\d{{4}}\b', re.I), 0.9),
        (re.compile(rf'\b\d{{1,2}}-{_MONTH}\b\.?-\d{{2,4}}\b', re.I), 1.0),
        (re.compile(rf'\b\d{{1,2}}(?:st|nd|rd|th)\s+day\s+of\s+{_MONTH}\b\.?,?\s+\d{{4}}\b', re.I), 1.0),
    ],
    'money': [
        (re.compile(r'(?:[$\u20ac\u00a3\u20b1\u00a5]|\b(?:USD|PHP|EUR|GBP|JPY|AUD|CAD|P)\b\.?)\s?\d[\d,]*(?:\.\d+)?', re.I), 1.0),
        (re.compile(r'\b\d[\d,]*(?:\.\d+)?\s?(?:USD|PHP|EUR|GBP|dollars?|pesos)\b', re.I), 1.0),
        (re.compile(r'(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w])|(?<![\w.])\d+(?:\.\d{1,2})?(?![\w])'), 0.85),
    ],
    'percent': [(re.compile(r'\d+(?:\.\d+)?\s?%'), 1.0)],
    'quantity': [(re.compile(r'\d+(?:[.,]\d+)*\s?[A-Za-z%]{0,10}'), 1.0)],
    'id': [(_ID_RE, 1.0)],
    'address': [
        (re.compile(r"\b\d+[A-Za-z]?(?:[-/]\d+)?\s+[\w.' -]+?\b(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|drive|dr|highway|hwy|court|ct|way|barangay|brgy)\b\.?", re.I), 0.9),
        (re.compile(r'\b(?:brgy|barangay|purok|sitio|blk|block|lot|phase|unit)\b\.?[^,\n]*(?:,[^,\n]+)+', re.I), 0.9),
        (re.compile(r'\d+[^,\n]*,\s*[A-Za-z][^\n]*'), 0.7),
        (re.compile(r"^[A-Z][\w .'-]+(?:,\s*[A-Z][\w .'-]+){1,5}(?:\s+\d{4,6})?$"), 0.7),
    ],
    'year': [
        (re.compile(r'\b(?:(?:A\.?\s?Y\.?|S\.?\s?Y\.?)\s*)?(?:19|20)\d{2}\s*[-\u2013/]\s*(?:(?:19|20)\d{2}|\d{2})\b', re.I), 1.0),
        (re.compile(r'\b(?:19|20)\d{2}\b'), 0.85),
    ],
    'term': [
        (re.compile(rf'\b(?:{_ORDINAL}|summer|mid-?year)\s+(?:sem(?:ester)?|term|trimester|quarter)\b', re.I), 1.0),
        (re.compile(r'\b(?:fall|spring|summer|winter|autumn)\s+(?:term\s+|semester\s+|sem\s+)?(?:19|20)\d{2}\b', re.I), 1.0),
        (re.compile(r'\b(?:sem(?:ester)?|term|trimester|quarter)\s*(?:[1-4]|i{1,3}|iv)\b', re.I), 1.0),
        (re.compile(r'\b(?:fall|spring|summer|winter|autumn|mid-?year|intersession)\b', re.I), 0.9),
        (re.compile(rf'(?<![\w.]){_ORDINAL}(?![\w])', re.I), 0.85),
    ],
    'year_level': [
        (re.compile(rf'\b{_ORDINAL}\s+year\b', re.I), 1.0),
        (re.compile(r'\byear\s*(?:[1-6]|i{1,3}|iv|v|vi)\b', re.I), 1.0),
        (re.compile(r'\bgrade\s*(?:[1-9]|1[0-2])\b', re.I), 1.0),
        (re.compile(r'\b(?:freshman|sophomore|junior|senior|undergraduate)\b', re.I), 0.9),
        (re.compile(rf'(?<![\w.]){_ORDINAL}(?![\w])', re.I), 0.85),
    ],
    'grade': [
        (re.compile(r'(?<![\w.])[0-5]\.\d{1,3}(?![\w])(?!\.\d)'), 1.0),
        (re.compile(r'(?<![\w.])\d{1,3}(?:\.\d+)?\s?%'), 1.0),
        (re.compile(r'(?<![\w.])(?:100|[5-9]\d)(?:\.\d+)?(?![\w.%])'), 0.85),
        (re.compile(r'(?<![\w])[A-DF][+-]?(?![\w])'), 0.85),
        (re.compile(r'\b(?:inc|drp|passed|failed|incomplete|dropped|withdrawn)\b', re.I), 0.85),
    ],
    'program': [
        (re.compile(rf"\b(?:bachelor|master|doctor|associate)(?:'s|s)?\s+(?:of|in)\s+{_PROGRAM_TAIL}", re.I), 1.0),
        (re.compile(r"\b(?:B\.?S\.?|B\.?A\.?|A\.?B\.?|M\.?S\.?|M\.?A\.?|Ph\.?D\.?|BSc|MSc|BEEd|BSEd|BSIT|BSCS|BSBA|BSN|BSA|BSE|BSCE|BSEE|BSME|BSHM|BSTM|BSCrim|BSIS|BSCpE|BSECE|ABM|STEM|HUMSS|TVL|MBA|MPA|MAEd|MIT|DIT|JD)(?![A-Za-z0-9])(?:\s*(?:in|of|major(?:ing)?\s+in|-)\s*[A-Za-z][A-Za-z&/'-]*(?:\s+[A-Za-z][A-Za-z&/'-]*){0,7})?", re.I), 1.0),
    ],
    'course_code': [(re.compile(r'\b[A-Z]{2,5}[\s-]?\d{2,4}[A-Z]?\b'), 1.0)],
}

_REFINABLE = {
    'email', 'phone', 'url', 'date', 'money', 'percent', 'year', 'term', 'year_level', 'grade',
    'course_code',
}
_NO_DISCOVERY = {'text', 'id', 'quantity', 'grade', 'course_code'}
_TITLE_FIELD_WORDS = {'title', 'thesis', 'research', 'dissertation', 'capstone', 'project', 'topic'}
_ENTITLED_RE = re.compile(
    r"(?:entitled|titled)\s*[:,]?\s*[\"\u201c\u2018']\s*(?P<title>[^\"\u201d\u2019\n]{5,200}?)\s*[\"\u201d\u2019']",
    re.I,
)

_CUE_RULES = [
    (
        {
            'student', 'applicant', 'graduate', 'candidate', 'awardee', 'recipient',
            'examinee', 'learner', 'enrollee',
        },
        {'person', 'name'},
        r'certif(?:y|ies)\s+that|awarded\s+to|conferred\s+(?:up)?on|presented\s+to|issued\s+to|'
        r'granted\s+to|submitted\s+by|prepared\s+by|recommend(?:ed|ing)?|endorse|nominat(?:e|ing)|'
        r'name\s+of\s+(?:the\s+)?(?:student|applicant)',
    ),
    (
        {'adviser', 'advisor', 'mentor'},
        {'person', 'name'},
        r'(?:advis(?:er|or)|mentor)\s*(?:is|:|,|-)?|under\s+the\s+(?:guidance|supervision)\s+of',
    ),
    (
        {'program', 'course', 'degree', 'major'},
        {'program'},
        r'degree\s+of|completed(?:\s+the)?|enrolled\s+(?:in|as)(?:\s+the)?|pursuing(?:\s+the)?|'
        r'program\s+of\s+study|course\s+of\s+study|student\s+of\s+the|requirements\s+for\s+the|'
        r'candidate\s+for\s+the',
    ),
    (
        {'graduation', 'graduated', 'conferred', 'completion'},
        {'date'},
        r'(?:graduated|conferred|awarded|completed)\b[^.;]{0,80}?\bon(?:\s+the)?|'
        r'(?:conferred|given|awarded|granted)\s*(?:on|this|upon)?(?:\s+the)?',
    ),
    (
        {'issued', 'issue', 'dated', 'certification', 'issuance'},
        {'date'},
        r'(?:issued|dated|signed|given)\s*(?:on|this)?(?:\s+the)?',
    ),
    (
        {'university', 'school', 'institution', 'college'},
        {'org'},
        r'graduated\s+from|enrolled\s+(?:at|in)|studied\s+at|student\s+of|from',
    ),
]
_TITLES = r'(?:(?:mr|ms|mrs|miss|dr|engr|atty|prof)\.?\s*)?'
_CUES = [
    (
        {_clean_token(word) for word in words},
        types,
        re.compile(rf'(?:{cue})\s*{_TITLES}$', re.I),
        re.compile(cue, re.I),
    )
    for words, types, cue in _CUE_RULES
]


def _pattern_matches(field_type, text):
    for pattern, weight in _PATTERNS.get(field_type, ()):
        for match in pattern.finditer(text):
            if (
                field_type == 'phone'
                and not 7 <= sum(char.isdigit() for char in match.group()) <= 15
            ):
                continue

            yield match.start(), match.end(), weight


def _pattern_coverage(field_type, value):
    value = value.strip()

    return max(
        (
            weight * (end - start) / max(len(value), 1)
            for start, end, weight in _pattern_matches(field_type, value)
        ),
        default=0.0,
    )


def _shape_coverage(field_type, value):
    text = value.title() if value.isupper() else value

    if field_type in ('person', 'name') and (_NAME_SHAPE_RE.match(text) or _NAME_COMMA_RE.match(text)):
        return 0.6

    if field_type in ('org', 'name') and _ORG_SUFFIX_RE.search(value):
        return 0.9

    if field_type in ('program', 'org') and _PROGRAM_WORDS_RE.search(value):
        return 0.6

    if field_type in ('org', 'location') and _CAPS_PHRASE_RE.match(text):
        return 0.45

    return 0.0


def _refine(field_type, value, entity_spans):
    if field_type not in _REFINABLE:
        return value, 0, len(value)

    matches = [
        (start, end) for start, end, weight in _pattern_matches(field_type, value)
        if weight >= (0.85 if field_type == 'year' else 0.9)
    ]

    if not matches and field_type == 'date':
        matches = [(start, end) for start, end, label in entity_spans if label == 'DATE']

    if not matches:
        return value, 0, len(value)

    start, end = max(matches, key=lambda span: span[1] - span[0])

    if end - start >= len(value) * 0.95:
        return value, 0, len(value)

    refined = value[start:end].strip()
    offset = len(value[start:end]) - len(value[start:end].lstrip())

    return refined, start + offset, start + offset + len(refined)


class _Context:
    """Reads entity spans from the document that was already processed by spaCy."""

    def __init__(self, doc):
        self.entities = tuple(
            (entity.start_char, entity.end_char, entity.label_) for entity in doc.ents
        )
        self.entity_starts = tuple(entity[0] for entity in self.entities)

    def entities_in(self, start, end):
        if start is None or end is None:
            return ()

        index = max(0, bisect_left(self.entity_starts, start) - 1)
        matches = []

        while index < len(self.entities):
            entity_start, entity_end, label = self.entities[index]

            if entity_start >= end:
                break

            if entity_end > start:
                matches.append(
                    (max(entity_start, start) - start, min(entity_end, end) - start, label)
                )

            index += 1

        return matches

    def entity_coverage(self, value, start=None, end=None):
        coverage = {}

        for left, right, label in self.entities_in(start, end):
            overlap = min(right, len(value)) - max(left, 0)

            if overlap > 0:
                share = overlap / max(len(value), 1)
                coverage[label] = max(coverage.get(label, 0.0), share)

        return coverage


def _find_hits(words, variants):
    hits = []

    for tokens, (quality, kind) in variants.items():
        size = len(tokens)

        for index in range(len(words) - size + 1):
            window = words[index:index + size]
            found = tuple(word[0] for word in window)
            start, end = window[0][1], window[-1][2]

            if found == tokens:
                hits.append(_Hit(start, end, quality, kind))
            elif kind in ('exact', 'partial') and sum(map(len, tokens)) >= 6:
                token_similarity = all(
                    SequenceMatcher(None, actual, expected).ratio() >= 0.75
                    for actual, expected in zip(found, tokens)
                )
                matcher = SequenceMatcher(None, ' '.join(found), ' '.join(tokens))

                if token_similarity and matcher.ratio() >= 0.8:
                    hits.append(_Hit(start, end, round(quality * matcher.ratio(), 2), 'fuzzy'))

    hits.sort(key=lambda hit: (-hit.quality, -(hit.end - hit.start)))
    chosen = []

    for hit in hits:
        if all(hit.end <= other.start or hit.start >= other.end for other in chosen):
            chosen.append(hit)

    return sorted(chosen, key=lambda hit: hit.start)


def _is_label_position(line, hit):
    before, after = line[:hit.start], line[hit.end:]

    return (
        not re.search(r'[A-Za-z0-9]', before)
        or _SEPARATOR_RE.match(after) is not None
        or re.search(r'(?:\s{2,}|\t)$', before) is not None
    )


_KEEP_PERIOD_RE = re.compile(
    r'(?:^|[\s,])(?:[A-Za-z]|jr|sr|inc|co|ltd|corp|st|ave|dr|prof|engr|atty|mr|ms|mrs|ma|ph\.d)\.$',
    re.IGNORECASE,
)


def _clean_value(value):
    value = re.sub(r'\s+', ' ', value)
    cleaned = value.strip(' \t:;,.-_|')

    if value.rstrip(' \t:;,-_|').endswith('.') and _KEEP_PERIOD_RE.search(cleaned + '.'):
        cleaned += '.'

    return cleaned


def _value_span(base_offset, source, value):
    position = source.find(value)

    if position < 0:
        return None, None

    start = base_offset + position

    return start, start + len(value)


def _next_nonblank(lines, index):
    return next(
        (position for position in range(index + 1, len(lines)) if lines[position].strip()),
        None,
    )


def _resolve_checkboxes(value):
    boxes = list(_BOX_RE.finditer(value))

    if not boxes:
        return value

    checked = [
        match.group(2).strip(' ,;/')
        for match in boxes
        if _CHECKED_BOX_RE.fullmatch(match.group(1))
    ]
    checked = [value for value in checked if value]

    return ', '.join(checked) if checked else None


def _aligned_cell(line, hit, next_line, hits_on_line):
    if not re.search(r'\s{2,}|\t', line.strip() + '  ' + next_line.strip()):
        return '', 0

    next_labels = [start for start, _ in hits_on_line if start > hit.start]
    region_end = min(next_labels) if next_labels else max(len(line), len(next_line))
    cells = re.finditer(r'\S+(?: \S+)*', next_line)
    best, best_start, overlap = '', 0, 0

    for cell in cells:
        current = min(cell.end(), region_end) - max(cell.start(), hit.start)

        if current > overlap:
            best, best_start, overlap = cell.group(), cell.start(), current

    return _clean_value(best), best_start


def _continuation(lines, last_index, line_hits, limit=2):
    extra = []

    for index in range(last_index + 1, min(len(lines), last_index + limit + 1)):
        if not lines[index].strip() or line_hits.get(index) or _LABEL_LIKE_RE.match(lines[index]):
            break

        extra.append(lines[index].strip())

    return extra


def _signature_candidates(hit, line_number, lines, line_hits, line_offsets, base):
    previous = line_number - 1
    skipped = 0

    while previous >= 0 and _PLACEHOLDER_RE.match(lines[previous].strip()) and skipped < 3:
        previous -= 1
        skipped += 1

    candidates = []

    if previous >= 0 and not line_hits.get(previous) and not _LABEL_LIKE_RE.match(lines[previous]):
        value = _clean_value(lines[previous])

        if value and not _PLACEHOLDER_RE.match(value):
            start, end = _value_span(line_offsets[previous], lines[previous], value)
            candidates.append({
                **base, 'text': value, 'source': 'above_label', 'line': previous + 1,
                'start': start, 'end': end, 'context': f'{base["label_text"]}: {value}',
            })

    following = _next_nonblank(lines, line_number)

    if following is not None and not line_hits.get(following) and not _LABEL_LIKE_RE.match(lines[following]):
        value = _clean_value(lines[following])

        if value and not _PLACEHOLDER_RE.match(value):
            start, end = _value_span(line_offsets[following], lines[following], value)
            candidates.append({
                **base, 'text': value, 'source': 'adjacent_below', 'line': following + 1,
                'start': start, 'end': end, 'context': f'{base["label_text"]}: {value}',
            })

    return candidates


def _line_candidates(spec, hit, line_number, lines, line_hits, line_offsets):
    line = lines[line_number]
    label_end = hit.end
    tail = re.match(
        r'(\s+(?:of|for|to|in|on|at|by|and)\s+[A-Za-z]+(?:\s+[A-Za-z]+){0,2})\s*:',
        line[label_end:],
        re.I,
    )

    if tail and not _SEPARATOR_RE.match(line, label_end):
        label_end += tail.end(1)

    label_text = line[hit.start:label_end]
    base = {'label_quality': hit.quality, 'label_kind': hit.kind, 'label_text': label_text}
    multiline = spec['type'] in ('address', 'text')
    separator = _SEPARATOR_RE.match(line, label_end)

    if spec['role'] and not separator and re.match(r'\s*(?:,.*)?$', line[label_end:]):
        return _signature_candidates(hit, line_number, lines, line_hits, line_offsets, base)

    self_labeled = (
        not separator and spec['type'] in ('org', 'program', 'location')
        and re.match(r'\s+(?:of|at)\b', line[label_end:], re.I) is not None
    )
    position = hit.start if self_labeled else (separator.end() if separator else label_end)
    junk = None if self_labeled else _LEAD_JUNK_RE.match(line, position)

    if junk:
        position = junk.end()

    raw = line[position:]
    cut = len(raw)

    for pattern in (_INLINE_LABEL_RE, _COLUMN_LABEL_RE):
        match = pattern.search(raw)

        if match:
            cut = min(cut, match.start())

    for start, _ in line_hits.get(line_number, ()):
        if 0 <= start - position and start != hit.start:
            cut = min(cut, start - position)

    raw_value = raw[:cut]
    value = _resolve_checkboxes(_clean_value(raw_value))

    if value is None:
        return []

    source, last = None, line_number
    value_start, value_end = _value_span(line_offsets[line_number] + position, raw_value, value)

    if value and not _PLACEHOLDER_RE.match(value):
        if not separator and not self_labeled and line.strip().isupper():
            return []

        source = 'label_linked' if separator else 'label_inline'
    else:
        value = ''
        following = _next_nonblank(lines, line_number)

        if following is None or line_hits.get(following) or _LABEL_LIKE_RE.match(lines[following]):
            return []

        next_line = lines[following]
        label_only = not re.search(r'[A-Za-z0-9]', line[:hit.start] + line[hit.end:])

        if label_only:
            raw_value, value_start_column = next_line, 0
            value, source = _clean_value(next_line), 'label_only_next_line'
        else:
            value, value_start_column = _aligned_cell(
                line, hit, next_line, line_hits.get(line_number, ())
            )
            source = 'aligned_column' if value else 'header_row_adjacent'

            if not value:
                raw_value, value_start_column = next_line, 0
                value = _clean_value(next_line)
            else:
                raw_value = next_line[value_start_column:]

        last = following
        value = _resolve_checkboxes(value)

        if not value or _PLACEHOLDER_RE.match(value):
            return []

        value_start, value_end = _value_span(
            line_offsets[following] + value_start_column, raw_value, value
        )

    if multiline and source != 'aligned_column':
        value = _clean_value(' '.join([value, *_continuation(lines, last, line_hits)]))

    return [{
        **base, 'text': value, 'source': source, 'line': line_number + 1,
        'start': value_start, 'end': value_end, 'context': f'{label_text}: {value}',
    }]


def _drop_swallowed_hits(specs):
    for spec in specs:
        for line_number, hits in list(spec['hits'].items()):
            kept = [
                hit for hit in hits
                if not any(
                    other.start <= hit.start and other.end >= hit.end
                    and other.end - other.start > hit.end - hit.start and other.quality >= 0.7
                    for other_spec in specs if other_spec is not spec
                    for other in other_spec['hits'].get(line_number, ())
                )
            ]

            if kept:
                spec['hits'][line_number] = kept
            else:
                del spec['hits'][line_number]


def _mark_qualified_hits(spec, lines):
    for line_number, hits in spec['hits'].items():
        for hit in hits:
            if hit.kind not in ('head', 'partial') and not (
                hit.kind == 'exact' and len(spec['tokens']) == 1
            ):
                continue

            prefix = re.split(r'\s{2,}|\t', lines[line_number][:hit.start])[-1]

            if re.search(r'[\d:\u2013\u2014]', prefix):
                continue

            words = re.findall(r"[A-Za-z]+(?:['\u2019]s)?", prefix)

            if 1 <= len(words) <= 3 and any(
                _clean_token(word) in _QUALIFIER_WORDS for word in words
            ):
                hit.quality = min(hit.quality, 0.45)
                hit.qualified = True


def _entity_targets(field_type, text, entities):
    expected = _ENTITY_LABELS.get(field_type, set())
    spans = [(start, end, f'ner:{label}') for start, end, label in entities if label in expected]
    spans.extend(
        (start, end, 'pattern')
        for start, end, weight in _pattern_matches(field_type, text)
        if weight >= 0.9
    )
    spans.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    kept = []

    for span in spans:
        if not kept or span[0] >= kept[-1][1]:
            kept.append(span)

    return kept


def _syntactic_closeness(doc, sentence, hit, start, end):
    label = doc.char_span(
        sentence.start_char + hit.start, sentence.start_char + hit.end, alignment_mode='expand'
    )
    value = doc.char_span(
        sentence.start_char + start, sentence.start_char + end, alignment_mode='expand'
    )

    if label is None or value is None:
        return 0.0

    ancestors = {token.i: depth for depth, token in enumerate([label.root, *label.root.ancestors])}

    for depth, token in enumerate([value.root, *value.root.ancestors]):
        if token.i in ancestors:
            steps = ancestors[token.i] + depth
            return 1.0 if steps <= 2 else 0.85 if steps <= 4 else 0.0

    return 0.0


def _sentence_candidates(spec, specs, doc, label_tokens, raw_text):
    if spec['type'] == 'text':
        return []

    candidates = []

    for sentence in doc.sents:
        words = _words(sentence.text)
        hits = [hit for hit in _find_hits(words, spec['variants']) if hit.quality >= 0.6]

        if not hits:
            continue

        other_labels = [
            (hit.start, hit.end)
            for other in specs if other is not spec
            for hit in _find_hits(words, other['variants'])
            if hit.quality >= 0.7
        ]
        entities = [
            (entity.start_char - sentence.start_char, entity.end_char - sentence.start_char, entity.label_)
            for entity in sentence.ents
        ]
        start_offset = sentence.start_char
        sentence_text = raw_text[start_offset:sentence.end_char]
        targets = _entity_targets(spec['type'], sentence_text, entities)

        for hit in hits:
            options = []

            for start, end, _ in targets:
                if start < hit.end and end > hit.start and not (start <= hit.start and end >= hit.end):
                    continue

                if _tokens(sentence_text[start:end]) in label_tokens:
                    continue

                after = start >= hit.end or (start < hit.end and end > hit.start)
                low, high = (hit.end, start) if after else (end, hit.start)

                if any(low <= left and right <= high for left, right in other_labels):
                    continue

                distance = max(0, high - low)
                options.append((distance + (0 if after else 15), start, end, distance, after))

            if not options:
                continue

            _, start, end, distance, after = min(options)
            proximity = max(1 / (1 + distance / 40), _syntactic_closeness(doc, sentence, hit, start, end))
            candidates.append({
                'text': sentence_text[start:end].strip(), 'source': 'sentence_context',
                'line': raw_text.count('\n', 0, start_offset + start) + 1,
                'label_quality': hit.quality, 'label_kind': hit.kind,
                'label_text': sentence.text[hit.start:hit.end],
                'proximity': proximity * (1.0 if after else 0.9),
                'start': start_offset + start, 'end': start_offset + end,
                'context': sentence_text,
            })

    return candidates


def _cue_before(spec, text, start):
    prefix = re.sub(r'\s+', ' ', text[max(0, start - 90):start])
    own = set(spec['tokens'])
    generic_name = spec['tokens'] in (('name',), ('person',))

    for words, types, regex, _ in _CUES:
        if (
            spec['type'] in types
            and (own & words or (generic_name and 'student' in words))
            and regex.search(prefix)
        ):
            return True

    return False


def _name_after_cue(spec, text):
    own = set(spec['tokens'])
    candidates = []

    for words, types, _, cue_pattern in _CUES:
        if spec['type'] not in types or not (
            own & words or (spec['tokens'] in (('name',), ('person',)) and 'student' in words)
        ):
            continue

        for match in cue_pattern.finditer(text):
            tail = re.match(r'\s*' + _TITLES + r'([^\n,;]{3,60})', text[match.end():], re.I)

            if tail and _shape_coverage(spec['type'], tail.group(1).strip()) >= 0.3:
                start = match.end() + tail.start(1)
                candidates.append((start, start + len(tail.group(1).rstrip())))

    return candidates


def _type_only_candidates(spec, doc, label_tokens, raw_text):
    candidates = []

    def add(start, end, source, quality):
        value = raw_text[start:end].strip()

        if value:
            candidates.append({
                'text': value, 'source': source,
                'line': raw_text.count('\n', 0, start) + 1,
                'label_quality': quality,
                'label_kind': 'cue' if source == 'cue_context' else 'none',
                'label_text': '', 'start': start, 'end': end, 'context': value,
            })

    if spec['type'] == 'text' and set(spec['tokens']) & _TITLE_FIELD_WORDS:
        for match in _ENTITLED_RE.finditer(raw_text):
            add(match.start('title'), match.end('title'), 'cue_context', 0.85)

    if spec['type'] in _NO_DISCOVERY:
        return candidates[:3]

    entities = [(entity.start_char, entity.end_char, entity.label_) for entity in doc.ents]
    targets = [
        (start, end) for start, end, _ in _entity_targets(spec['type'], raw_text, entities)
        if _tokens(raw_text[start:end]) not in label_tokens
    ]
    cued = [(start, end) for start, end in targets if _cue_before(spec, raw_text, start)]

    if not cued and spec['type'] in ('person', 'name'):
        cued = _name_after_cue(spec, raw_text)

    plain = [target for target in targets if target not in cued]

    candidates.extend(
        {
            'text': raw_text[start:end].strip(), 'source': 'cue_context',
            'line': raw_text.count('\n', 0, start) + 1, 'label_quality': 0.7,
            'label_kind': 'cue', 'label_text': '', 'start': start, 'end': end,
            'context': raw_text[max(0, start - 90):end],
        }
        for start, end in cued[:3]
    )
    candidates.extend(
        {
            'text': raw_text[start:end].strip(), 'source': 'type_only',
            'line': raw_text.count('\n', 0, start) + 1, 'label_quality': 0.3,
            'label_kind': 'none', 'label_text': '', 'start': start, 'end': end,
            'context': raw_text[start:end],
        }
        for start, end in plain[:3]
    )

    return candidates[:6]


_STRUCTURE = {
    'label_linked': 0.9, 'label_only_next_line': 0.8, 'aligned_column': 0.8,
    'label_inline': 0.7, 'sentence_context': 0.6, 'header_row_adjacent': 0.5,
    'type_only': 0.3, 'above_label': 0.7, 'adjacent_below': 0.4,
    'cue_context': 0.7,
}


def _type_score(field_type, value, start, end, ctx):
    entities = ctx.entity_coverage(value, start, end)

    if field_type == 'text':
        if max(entities.values(), default=0.0) >= 0.7:
            return 0.8, 'ner', entities

        return 0.7, 'untyped', entities

    expected = _ENTITY_LABELS.get(field_type, set())
    ner = max((coverage for label, coverage in entities.items() if label in expected), default=0.0)
    other = max((coverage for label, coverage in entities.items() if label not in expected), default=0.0)
    pattern = _pattern_coverage(field_type, value)
    best = max(ner, pattern)

    if best >= 0.3:
        return 0.55 + 0.45 * min(best, 1.0), ('ner' if ner >= pattern else 'pattern'), entities

    shape = _shape_coverage(field_type, value)

    if shape >= 0.3:
        if other >= 0.6:
            return 0.45, 'conflict', entities

        return 0.55 + 0.45 * shape, 'shape', entities

    if other >= 0.6:
        return 0.2, 'conflict', entities

    return 0.3, 'no-evidence', entities


def _plausibility(value, field_type):
    if not value:
        return 0.0

    if sum(char.isalnum() for char in value) / len(value) < 0.5:
        return 0.2

    return 0.3 if len(value) > (400 if field_type in ('text', 'address') else 120) else 1.0


def _looks_like_header(value, field_type, label_tokens, start, end, ctx):
    if len(value) > 48:
        return False

    if _tokens(value) in label_tokens:
        return True

    if value.isupper() and not any(char.isdigit() for char in value) and len(value.split()) <= 4:
        if max(_pattern_coverage(field_type, value), _shape_coverage(field_type, value)) >= 0.6:
            return False

        if field_type in ('person', 'name', 'org') and len(value.split()) >= 2:
            return False

        return not ctx.entity_coverage(value, start, end)

    return False


def _score(candidate, spec, label_tokens, ctx):
    value = candidate['text']
    type_score, evidence_tag, entities = _type_score(
        spec['type'], value, candidate.get('start'), candidate.get('end'), ctx
    )
    quality = candidate['label_quality']
    confidence = (
        0.30 * _STRUCTURE[candidate['source']]
        + 0.40 * type_score
        + 0.10 * _plausibility(value, spec['type'])
        + 0.20 * quality
    )
    confidence = min(confidence, 0.45 + 0.55 * quality)

    if 'proximity' in candidate:
        confidence *= 0.7 + 0.3 * candidate['proximity']

    if candidate['source'] not in ('sentence_context', 'type_only') and _looks_like_header(
        value, spec['type'], label_tokens, candidate.get('start'), candidate.get('end'), ctx
    ):
        confidence *= 0.4
        evidence_tag = 'header-like'

    candidate['confidence'] = round(min(confidence, 0.99), 2)
    candidate['evidence'] = {
        'label_match': candidate['label_kind'],
        'label_quality': round(quality, 2),
        'layout': candidate['source'],
        'expected_type': spec['type'],
        'type_match': evidence_tag,
        'type_score': round(type_score, 2),
        'entities': {label: round(coverage, 2) for label, coverage in entities.items()},
    }

    return candidate


def _score_all(candidates, spec, label_tokens, ctx):
    if len(candidates) > MAX_SCORED_CANDIDATES:
        candidates = sorted(
            candidates,
            key=lambda item: -item['label_quality'] * _STRUCTURE[item['source']],
        )[:MAX_SCORED_CANDIDATES]

    for candidate in candidates:
        start, end = candidate.get('start'), candidate.get('end')
        entity_spans = ctx.entities_in(start, end)
        refined, left, right = _refine(spec['type'], candidate['text'], entity_spans)

        if refined != candidate['text']:
            candidate['text'] = refined

            if start is not None and end is not None:
                candidate['start'], candidate['end'] = start + left, start + right

    return [_score(candidate, spec, label_tokens, ctx) for candidate in candidates]


def _rank(candidates):
    best = {}

    for candidate in candidates:
        key = _normalize(candidate['text'])

        if key and (key not in best or candidate['confidence'] > best[key]['confidence']):
            best[key] = candidate

    return sorted(best.values(), key=lambda item: (-item['confidence'], item['line']))


_TYPE_LABEL = {
    'money': 'amount of money', 'org': 'organization name', 'person': "person's name",
    'name': 'name', 'id': 'ID or code', 'quantity': 'quantity',
    'year': 'academic year', 'term': 'semester or term', 'year_level': 'year level',
    'grade': 'grade', 'program': 'program or degree', 'course_code': 'course code',
}


def _explain(state, ranked, spec):
    if state == 'missing':
        return 'Required field was not found near its label.'

    reliable = [item for item in ranked if item['confidence'] >= FOUND_AT]
    plausible = [item for item in ranked if item['confidence'] >= UNCERTAIN_AT]

    if state == 'ambiguous' or (
        len(plausible) > 1 and ranked[0]['evidence']['type_match'] not in ('no-evidence', 'conflict')
    ):
        values = ', '.join(f'"{item["text"]}"' for item in (reliable or plausible)[:3])
        return f'Several different values look possible: {values}.'

    best = ranked[0]
    evidence = best['evidence']

    if evidence['type_match'] in ('no-evidence', 'conflict', 'header-like'):
        kind = _TYPE_LABEL.get(spec['type'], spec['type'])
        return f'Found "{best["text"]}" but it does not look like {"a " if kind[:1] not in "aeiou" else "an "}{kind}.'

    if best['source'] == 'type_only':
        kind = _TYPE_LABEL.get(spec['type'], spec['type'])
        return f'Only an unlabeled {kind} ("{best["text"]}") was found; the label is missing.'

    if best['label_quality'] < 0.7:
        return f'Found "{best["text"]}" but the label only loosely matches "{spec["name"]}".'

    return f'Found "{best["text"]}" but confidence ({best["confidence"]}) is below {FOUND_AT}; the layout made the value hard to pin down.'


def _decide(spec, ranked):
    reliable = [item for item in ranked if item['confidence'] >= FOUND_AT]

    if reliable and not (
        len(reliable) > 1 and reliable[0]['confidence'] - reliable[1]['confidence'] < AMBIGUITY_GAP
    ):
        state = 'found'
    elif reliable:
        state = 'ambiguous'
    elif ranked and ranked[0]['confidence'] >= UNCERTAIN_AT:
        state = 'uncertain'
    else:
        state = 'missing'

    public = [
        {
            'text': item['text'], 'confidence': item['confidence'],
            'source': item['source'], 'line': item['line'],
            'reliable': item['confidence'] >= FOUND_AT, 'evidence': item['evidence'],
        }
        for item in ranked[:MAX_CANDIDATES]
    ]

    return state, {
        'mode': spec['mode'], 'required': spec['mode'] == 'required',
        'type': spec['type'], 'state': state, 'found': state == 'found',
        'confidence': ranked[0]['confidence'] if ranked else 0.0,
        'values': [item['text'] for item in reliable],
        'best': public[0] if public else None, 'candidates': public,
    }


def _caps_to_title(text):
    lines = []

    for line in text.split('\n'):
        title = line.title()

        if (
            line.isupper()
            and len(line.split()) >= 2
            and len(title) == len(line)
            and sum(char.isalpha() for char in line) >= 4
        ):
            line = title

        lines.append(line)

    return '\n'.join(lines)


def _instruction_review(errors):
    return {
        'status': 'REVIEW', 'fields': {}, 'missing_fields': [], 'uncertain_fields': [],
        'recheck': [{'field': 'validation_instructions', 'reason': error} for error in errors],
        'unrecognized_instructions': errors,
    }


def _manual_review_result(fields, reason):
    specs = [_build_spec(field) for field in fields]
    results = {
        spec['name']: {
            'mode': spec['mode'], 'required': spec['mode'] == 'required',
            'type': spec['type'], 'state': 'uncertain', 'found': False,
            'confidence': 0.0, 'values': [], 'best': None, 'candidates': [],
        }
        for spec in specs
    }
    required_fields = [field['name'] for field in fields if field['mode'] == 'required']

    return {
        'status': 'REVIEW', 'fields': results, 'missing_fields': [],
        'uncertain_fields': required_fields,
        'recheck': [{'field': name, 'reason': reason} for name in required_fields],
        'unrecognized_instructions': [],
    }


def validate_document_text(text, instructions):
    if not text or not text.strip():
        raise DocumentValidationError('No extracted text is available for validation.')

    fields, errors = parse_validation_instructions(instructions)

    if errors:
        return _instruction_review(errors)

    if not any(field['mode'] == 'required' for field in fields):
        return _instruction_review(
            ['Add at least one required field when document validation is enabled.']
        )

    raw_text = text.replace('\r\n', '\n').replace('\r', '\n')
    nlp = _load_model()

    if len(raw_text) > nlp.max_length:
        return _manual_review_result(
            fields,
            'Automatic validation was skipped because the extracted text is too long. '
            'Please review this field manually.',
        )

    doc = nlp(_caps_to_title(raw_text))
    doc.user_data['raw'] = raw_text
    context = _Context(doc)
    raw_lines = raw_text.split('\n')
    lines = [line.rstrip() for line in raw_lines]
    line_offsets = []
    offset = 0

    for line in raw_lines:
        line_offsets.append(offset)
        offset += len(line) + 1

    line_words = [_words(line) for line in lines]
    specs = [_build_spec(field) for field in fields]
    label_tokens = {tokens for spec in specs for tokens in spec['variants']}

    for spec in specs:
        spec['hits'] = {
            index: hits for index, words in enumerate(line_words)
            if (hits := _find_hits(words, spec['variants']))
        }

    _drop_swallowed_hits(specs)

    for spec in specs:
        _mark_qualified_hits(spec, lines)
        heads = [
            hit for index, hits in spec['hits'].items() for hit in hits
            if hit.kind == 'head' and not hit.qualified and _is_label_position(lines[index], hit)
        ]
        strong = any(
            hit.quality >= 0.7
            and (hit.kind in ('exact', 'alias') or _SEPARATOR_RE.match(lines[index], hit.end))
            for index, hits in spec['hits'].items() for hit in hits
        )

        if len(heads) == 1 and not strong:
            heads[0].quality = 0.7

    line_hits = defaultdict(list)

    for spec in specs:
        for index, hits in spec['hits'].items():
            line_hits[index].extend(
                (hit.start, hit.end) for hit in hits
                if hit.quality >= 0.7 and _is_label_position(lines[index], hit)
            )

    results, missing, uncertain, recheck = {}, [], [], []

    for spec in specs:
        raw_candidates = [
            candidate
            for index, hits in spec['hits'].items()
            for hit in hits if _is_label_position(lines[index], hit)
            for candidate in _line_candidates(spec, hit, index, lines, line_hits, line_offsets)
        ]
        ranked = _rank(_score_all(raw_candidates, spec, label_tokens, context))

        if not ranked or ranked[0]['confidence'] < UNCERTAIN_AT:
            sentence_candidates = _sentence_candidates(spec, specs, doc, label_tokens, raw_text)
            ranked = _rank(ranked + _score_all(sentence_candidates, spec, label_tokens, context))

        has_own_label = any(
            hit.quality >= 0.7 and _is_label_position(lines[index], hit)
            for index, hits in spec['hits'].items() for hit in hits
        )

        if (not ranked or ranked[0]['confidence'] < UNCERTAIN_AT) and not has_own_label:
            type_candidates = _type_only_candidates(spec, doc, label_tokens, raw_text)
            ranked = _rank(ranked + _score_all(type_candidates, spec, label_tokens, context))

        state, result = _decide(spec, ranked)
        results[spec['name']] = result

        if spec['mode'] == 'required' and state != 'found':
            (missing if state == 'missing' else uncertain).append(spec['name'])
            recheck.append({'field': spec['name'], 'reason': _explain(state, ranked, spec)})

    return {
        'status': 'REVIEW' if missing or uncertain else 'PASSED',
        'fields': results,
        'missing_fields': missing,
        'uncertain_fields': uncertain,
        'recheck': recheck,
        'unrecognized_instructions': [],
    }

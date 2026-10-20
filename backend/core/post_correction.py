import re
from functools import lru_cache
from importlib import resources

SKIP_ABOVE_SCORE = 0.95
MIN_WORD_LENGTH = 5
MIN_FREQUENCY = 500_000

LETTERS = re.compile(r'[A-Za-z]+')
SECTION_LABEL = re.compile(r'\b([A-Z])\.([A-Z]{3,})')
GLUED_WORDS = re.compile(r'\b([A-Z]?[a-z]{3,})([A-Z][a-z]{2,})\b')


@lru_cache(maxsize=1)
def _dictionary():
    from symspellpy import SymSpell

    symspell = SymSpell(max_dictionary_edit_distance=1)
    path = resources.files('symspellpy') / 'frequency_dictionary_en_82_765.txt'
    symspell.load_dictionary(str(path), term_index=0, count_index=1)
    return symspell


@lru_cache(maxsize=1)
def _spacy():
    import spacy

    return spacy.load('en_core_web_sm', disable=['parser', 'lemmatizer'])


def _is_candidate(word, names):
    lower = word.lower()
    return (
        word.isascii() and word.isalpha()
        and len(word) >= MIN_WORD_LENGTH
        and (word.islower() or word.istitle())
        and lower not in _dictionary().words
        and lower not in names
    )


def _suggest(word):
    from symspellpy import Verbosity

    matches = _dictionary().lookup(word.lower(), Verbosity.CLOSEST, max_edit_distance=1)
    if len(matches) != 1:
        return None
    match = matches[0]
    if match.distance != 1 or match.count < MIN_FREQUENCY:
        return None
    return match.term.capitalize() if word[0].isupper() else match.term


def _fix_spacing(line):
    known = _dictionary().words

    def split_glued(match):
        left, right = match[1], match[2]
        
        if (left + right).lower() in known or left.lower() not in known:
            return match[0]
        return f'{left} {right}'

    line = SECTION_LABEL.sub(r'\1. \2', line)
    return GLUED_WORDS.sub(split_glued, line)


def _fix_spelling(doc, names):
    line = doc.text
    for token in reversed(doc):
        if not _is_candidate(token.text, names):
            continue
        if token.pos_ == 'PROPN' or token.ent_type_:
            continue
        fix = _suggest(token.text)
        if fix:
            end = token.idx + len(token.text)
            line = line[:token.idx] + fix + line[end:]
    return line


def _is_worth_checking(line, score, names):
    if score is not None and score >= SKIP_ABOVE_SCORE:
        return False
    return any(_is_candidate(word, names) for word in LETTERS.findall(line))


def correct_lines(lines, scores, names):
    names = {name.lower() for name in names}
    lines = [_fix_spacing(line) for line in lines]

    to_check = [i for i, line in enumerate(lines) if _is_worth_checking(line, scores[i], names)]
    if to_check:
        docs = _spacy().pipe((lines[i] for i in to_check), batch_size=64)
        for i, doc in zip(to_check, docs):
            lines[i] = _fix_spelling(doc, names)

    return '\n'.join(lines)
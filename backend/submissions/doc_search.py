import re

from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db.models import Exists, OuterRef

from submissions.models import DocumentMetadata

SEARCH_MODES = (
    ("full_text", 'Full-text search'),
    ("fuzzy", 'Fuzzy search'),
    ("title", 'Requirement title')
)
SEARCH_MODE_VALUES = {value for value, _label in SEARCH_MODES}
MAX_FUZZY_TERMS = 8


def _latest_submission_metadata():
    newer_version = DocumentMetadata.objects.filter(
        submission_id=OuterRef('submission_id'),
        version_number__gt=OuterRef('version_number')
    )
    
    return (
        DocumentMetadata.objects
        .filter(submission__isnull=False)
        .exclude(Exists(newer_version))
    )


def search_documents(submissions, query, mode='full_text'):
    query = (query or "").strip()
    if not query:
        return submissions
    if mode not in SEARCH_MODE_VALUES:
        mode = 'full_text'

    if mode == 'title':
        return submissions.filter(requirement__requirement_title__icontains=query)

    metadata = _latest_submission_metadata().filter(
        submission_id__in=submissions.order_by().values('pk')
    )

    if mode == 'fuzzy':
        terms = re.findall(r"[\w']+", query, flags=re.UNICODE)[:MAX_FUZZY_TERMS]
        if not terms:
            return submissions.none()
        for term in terms:
            metadata = metadata.filter(
                extracted_text__trigram_strict_word_similar=term
            )
    else:
        metadata = metadata.annotate(
            search_vector=SearchVector('extracted_text', config='english')
        ).filter(
            search_vector=SearchQuery(query, config='english', search_type='websearch')
        )

    return submissions.filter(pk__in=metadata.values('submission_id'))


def filter_by_content(submissions, text):
    return search_documents(submissions, text, mode='full_text')
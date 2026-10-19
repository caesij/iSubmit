import re

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models.functions import Coalesce

from django.db.models import (
    Case,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
    When
)

from submissions.models import DocumentMetadata


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
        .order_by()
    )


def _matched_term_count(field, terms):
    return sum(
        (
            Case(
                When(**{f'{field}__trigram_strict_word_similar': term}, then=1),
                default=0,
                output_field=IntegerField(),
            )
            for term in terms
        ),
        Value(0)
    )


def search_documents(submissions, query, sort_by='newest'):
    query = (query or '').strip()
    
    if not query:
        return submissions.order_by('initially_submitted_at' if sort_by == 'oldest' else '-initially_submitted_at')

    terms = re.findall(r"[\w']+", query, flags=re.UNICODE)[:MAX_FUZZY_TERMS]
    search_vector = SearchVector('extracted_text', config='english')
    search_query = SearchQuery(query, config='english', search_type='websearch')

    metadata = _latest_submission_metadata().filter(submission_id=OuterRef('pk'))
    
    full_text_matches = (
        metadata
        .annotate(
            search_vector=search_vector,
            search_rank=SearchRank(search_vector, search_query),
        )
        .filter(search_vector=search_query)
    )
    
    fuzzy_text_matches = None
    fuzzy_title_matches = Q()
    fuzzy_text_terms = Q()
    fuzzy_title_count = Value(0, output_field=IntegerField())

    if terms:
        for term in terms:
            fuzzy_text_terms |= Q(extracted_text__trigram_strict_word_similar=term)
            fuzzy_title_matches |= Q(requirement__requirement_title__trigram_strict_word_similar=term)
            
        fuzzy_text_matches = (
            metadata
            .filter(fuzzy_text_terms)
            .annotate(matched_term_count=_matched_term_count('extracted_text', terms))
        )
        
        fuzzy_title_count = _matched_term_count('requirement__requirement_title', terms)

    annotations = {
        'full_text_match': Exists(full_text_matches),
        'full_text_rank': Coalesce(
            Subquery(full_text_matches.values('search_rank')[:1]),
            Value(0.0)
        ),
        'fuzzy_title_count': fuzzy_title_count,
        'match_tier': Case(
            When(requirement__requirement_title__icontains=query, then=0),
            When(full_text_match=True, then=1),
            default=2,
            output_field=IntegerField()
        )
    }
    
    if fuzzy_text_matches is not None:
        annotations['fuzzy_text_count'] = Coalesce(
            Subquery(fuzzy_text_matches.values('matched_term_count')[:1]),
            Value(0)
        )
    else:
        annotations['fuzzy_text_count'] = Value(0)

    results = submissions.annotate(**annotations)
    
    matches = (
        Q(requirement__requirement_title__icontains=query)
        | Q(full_text_match=True)
    )
    
    if terms:
        matches |= (fuzzy_title_matches | Q(pk__in=Subquery(fuzzy_text_matches.values('submission_id'))))

    date_ordering = ('initially_submitted_at' if sort_by == 'oldest' else '-initially_submitted_at')
    
    return results.filter(matches).order_by(
        'match_tier',
        '-full_text_rank',
        '-fuzzy_title_count',
        '-fuzzy_text_count',
        date_ordering
    )
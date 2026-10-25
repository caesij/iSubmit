from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render

from submissions.models import Requirement
from submissions.doc_search import search_documents
from submissions.querysets import active_document_queryset

def _render_repository(request, submissions, template_name, academic_year, document_type):
    submissions = active_document_queryset(submissions)
    search_query = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort_by', 'newest')

    if academic_year:
        submissions = submissions.filter(requirement__academic_year=f'A.Y. {academic_year}')
    if document_type:
        submissions = submissions.filter(
            document_file__iendswith=f'.{document_type.lower()}'
        )
    if search_query:
        submissions = search_documents(submissions, search_query, sort_by)
    else:
        submissions = submissions.order_by(
            'initially_submitted_at' if sort_by == 'oldest' else '-initially_submitted_at'
        )

    if not submissions.exists():
        messages.info(request, 'No documents match your filters.')

    page_obj = Paginator(submissions, 7).get_page(request.GET.get('page'))
    
    return render(request, template_name, {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'academic_years': Requirement.objects.values_list(
            'academic_year', flat=True
        ).distinct().order_by('-academic_year'),
        'document_type_choices': ['PDF', 'DOC', 'DOCX', 'XLSX'],
        'selected_academic_year': academic_year,
        'selected_document_type': document_type,
        'selected_sort_by': sort_by,
        'search_query': search_query,
    })
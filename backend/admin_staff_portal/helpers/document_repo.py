from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import render, redirect

from accounts.models import FacultyProfile
from admin_staff_portal.helpers.doc_repo_search import search_documents
from submissions.models import DocumentSubmission, SubmissionPeriod


def _document_redirect(archived):
    return redirect(
        'admin_staff_portal:document_archive'
        if archived
        else 'admin_staff_portal:document_repo'
    )


def _selected_ids(request):
    return request.POST.getlist('document_ids')


def get_document_queryset(request, *, archived=False):
    params = request.GET

    submissions = (
        DocumentSubmission.objects.filter(
            status=DocumentSubmission.SubmissionStatus.APPROVED,
            is_archived=archived
        )
        .select_related(
            'requirement__period',
            'faculty',
            'faculty__faculty_profile'
        )
    )

    if params.get('semester'):
        submissions = submissions.filter(
            requirement__period__semester=params['semester']
        )

    if params.get('academic_year'):
        submissions = submissions.filter(
            requirement__period__academic_year=params['academic_year']
        )

    if params.get('faculty_type'):
        submissions = submissions.filter(
            faculty__faculty_profile__faculty_type=params['faculty_type']
        )

    search_query = params.get('q', '').strip()
    sort_by = params.get('sort_by', 'newest')

    if search_query:
        return search_documents(submissions, search_query, sort_by)

    return submissions.order_by(
        'initially_submitted_at'
        if sort_by == 'oldest'
        else '-initially_submitted_at'
    )


def render_document_list(request, *, template_name, archived=False):
    page_obj = Paginator(
        get_document_queryset(request, archived=archived),
        7
    ).get_page(request.GET.get('page'))

    if not page_obj.object_list:
        messages.info(
            request,
            (
                'No archived documents match your filters.'
                if archived
                else 'No approved documents match your filters.'
            )
        )

    return render(request, template_name, {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'is_archive': archived,

        'semesters': SubmissionPeriod.Semester.choices,

        'academic_years': (
            SubmissionPeriod.objects
            .values_list('academic_year', flat=True)
            .distinct()
            .order_by('-academic_year')
        ),

        'faculty_type_choices': FacultyProfile.FacultyType.choices,

        'selected_semester': request.GET.get('semester', ''),
        'selected_academic_year': request.GET.get('academic_year', ''),
        'selected_faculty_type': request.GET.get('faculty_type', ''),
        'selected_sort_by': request.GET.get('sort_by', 'newest'),
        'search_query': request.GET.get('q', '').strip()
    })

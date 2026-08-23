from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Count, Q

from accounts.decorators import faculty
from submissions.models import DocumentSubmission

from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Q

from accounts.decorators import faculty
from submissions.models import DocumentSubmission


@faculty
@require_http_methods(['GET'])
def recent_submissions_list(request):
    all_submissions = DocumentSubmission.objects.filter(faculty=request.user)
    
    if not all_submissions.exists():
        messages.info(request, 'No recent submission to show')

    stats = all_submissions.aggregate(
        total_submitted=Count('id'),
        under_review=Count('id', filter=Q(status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW)),
        approved=Count('id', filter=Q(status=DocumentSubmission.SubmissionStatus.APPROVED)),
        returned=Count('id', filter=Q(status=DocumentSubmission.SubmissionStatus.NEEDS_REVISION)),
    )

    submitted_documents = all_submissions.select_related('requirement', 'reviewed_by')

    submission_status = request.GET.get('status')
    category = request.GET.get('category')
    sort_by = request.GET.get('sort', 'newest')

    if submission_status:
        submitted_documents = submitted_documents.filter(status=submission_status)
    if category:
        submitted_documents = submitted_documents.filter(requirement__category=category)

    if sort_by == 'oldest':
        submitted_documents = submitted_documents.order_by('initially_submitted_at')
    elif sort_by == 'deadline':
        submitted_documents = submitted_documents.order_by('requirement__deadline')
    else:
        submitted_documents = submitted_documents.order_by('-initially_submitted_at')

    context = {
        'submitted_documents': submitted_documents,
        'stats': stats,
        'categories': DocumentSubmission.objects.filter(faculty=request.user)
            .values_list('requirement__category', flat=True).distinct(),
        'status_choices': DocumentSubmission.SubmissionStatus.choices,
    }
    
    return render(
        request,
        'faculty_portal/core/my_submissions/recent_submissions_list.html',
        context
    )


@faculty
@require_http_methods(['GET'])
def view_my_submitted_document(request, document_id):
    submitted_document = get_object_or_404(
        DocumentSubmission,
        pk=document_id,
        faculty=request.user
    )
    context = {'submitted_document': submitted_document}
    return render(
        request,
        'faculty_portal/core/my_submissions/view_my_submitted_document.html',
        context
    )
    
@faculty
@require_http_methods(['GET'])
def view_my_submitted_document(request, document_id):
    submitted_document = get_object_or_404(
        DocumentSubmission,
        pk=document_id,
        faculty=request.user
    )
    
    context = {'submitted_document': submitted_document}
    
    return render(
        request,
        'faculty_portal/core/my_submissions/view_my_submitted_document.html',
        context
    )
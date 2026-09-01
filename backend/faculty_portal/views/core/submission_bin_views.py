from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.db import transaction
from django.core.files.base import ContentFile

from accounts.decorators import faculty
from submissions.models import Requirement, DraftUpload, DocumentSubmission
from submissions.forms import DraftUploadForm

@faculty
@require_http_methods(['GET'])
def upload_files_view(request):
    already_submitted_ids = DocumentSubmission.objects.filter(
        faculty=request.user
    ).values_list('requirement_id', flat=True)
    
    requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE,
    ).filter(
        Q(assigned_to=Requirement.AssignedFacultyType.ALL) |
        Q(assigned_to=request.user.faculty_type)
    ).exclude(
        id__in=already_submitted_ids
    ).order_by('deadline')

    drafts_by_requirement = {
        d.requirement_id: d
        for d in DraftUpload.objects.filter(
            faculty=request.user,
            requirement__in=requirements
        )
    }

    rows = [
        {'requirement': req, 'draft': drafts_by_requirement.get(req.id)}
        for req in requirements
    ]

    context = {'rows': rows}
    return render(
        request,
        'faculty_portal/core/submission_bin/upload_files.html',
        context
    )

@faculty
@require_http_methods(['POST'])
def attach_document_view(request, requirement_id):
    requirement = get_object_or_404(
        Requirement,
        pk=requirement_id,
        status=Requirement.ReqStatus.ACTIVE,
    )
    if requirement.assigned_to not in (Requirement.AssignedFacultyType.ALL, request.user.faculty_type):
        return HttpResponseForbidden('You are not assigned to this requirement.')

    draft, _ = DraftUpload.objects.get_or_create(
        faculty=request.user,
        requirement=requirement
    )

    form = DraftUploadForm(
        request.POST,
        request.FILES,
        instance=draft
    )
    if form.is_valid():
        form.save()
        messages.success(request, 'File attached successfully.')
    else:
        messages.error(request, 'Failed to upload file. Please check the format and size.')

    return redirect('faculty_portal:upload_files')

@faculty
@require_http_methods(['POST'])
def replace_document_view(request, document_id):
    draft = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user
    )

    form = DraftUploadForm(
        request.POST,
        request.FILES,
        instance=draft
    )
    
    if form.is_valid():
        form.save()
        messages.success(request, 'File replaced successfully.')
    else:
        messages.error(request, 'Failed to replace file.')

    return redirect('faculty_portal:upload_files')

@faculty
@require_http_methods(['GET', 'POST'])
def confirm_submission(request):
    already_submitted_ids = DocumentSubmission.objects.filter(
        faculty=request.user
    ).values_list('requirement_id', flat=True)
    
    requirements = Requirement.objects.filter(
        status=Requirement.ReqStatus.ACTIVE,
    ).filter(
        Q(assigned_to=Requirement.AssignedFacultyType.ALL) |
        Q(assigned_to=request.user.faculty_type)
    ).exclude(
        id__in=already_submitted_ids
    ).order_by('deadline')

    if not requirements.exists():
        messages.warning(request, 'You have no active requirements to submit.')
        return redirect('faculty_portal:upload_files')

    drafts_by_requirement = {
        d.requirement_id: d
        for d in DraftUpload.objects.filter(
            faculty=request.user,
            requirement__in=requirements
        )
    }

    rows = []
    all_ready = True
    for req in requirements:
        draft = drafts_by_requirement.get(req.id)
        is_ready = bool(draft and draft.draft_file)
        if not is_ready:
            all_ready = False
        rows.append({'requirement': req, 'draft': draft, 'is_ready': is_ready})

    if request.method == 'POST':
        if not all_ready:
            messages.error(request, 'All documents must be ready before you can submit.')
            return redirect('faculty_portal:review_confirm')

        try:
            created_submissions = []
            with transaction.atomic():
                for row in rows:
                    draft = row['draft']

                    draft.draft_file.open('rb')
                    file_content = ContentFile(draft.draft_file.read())
                    original_name = draft.draft_file.name.split('/')[-1]
                    draft.draft_file.close()

                    submission, created = DocumentSubmission.objects.get_or_create(
                        faculty=request.user,
                        requirement=row['requirement'],
                        defaults={'status': DocumentSubmission.SubmissionStatus.SUBMITTED}
                    )
                    submission.document_file.save(original_name, file_content, save=True)
                    created_submissions.append(submission)

                    draft.draft_file.delete(save=False)
                    draft.delete()
                    
                DraftUpload.objects.filter(faculty=request.user, requirement__in=requirements).delete()

            request.session['recently_submitted_ids'] = [str(s.id) for s in created_submissions]

            messages.success(request, 'Documents submitted successfully.')
            return redirect('faculty_portal:submission_complete')

        except Exception:
            messages.error(request, 'An error occurred while processing your submission. Please try again.')
            return redirect('faculty_portal:review_confirm')

    context = {'rows': rows, 'all_ready': all_ready}
    
    return render(
        request,
        'faculty_portal/core/submission_bin/review_confirm.html',
        context
    )
        
@faculty
@require_http_methods(['GET'])
def submission_complete(request):
    submitted_ids = request.session.pop('recently_submitted_ids', [])
    submitted_documents = DocumentSubmission.objects.filter(
        faculty=request.user,
        id__in=submitted_ids
    ).select_related('requirement').order_by('-initially_submitted_at')

    if not submitted_documents.exists():
        messages.info(request, 'No recent submission to show.')
        return redirect('faculty_portal:upload_files')

    context = {'submitted_documents': submitted_documents}
    
    return render(
        request,
        'faculty_portal/core/submission_bin/submission_complete.html',
        context
    )
        
@faculty
@require_http_methods(['GET'])
def view_uploaded_document(request, document_id):
    uploaded_document = get_object_or_404(
        DraftUpload,
        pk=document_id,
        faculty=request.user,
    )
    
    context = {'uploaded_document': uploaded_document}
    
    return render(
        request,
        'faculty_portal/core/submission_bin/view_uploaded_document.html',
        context
    )
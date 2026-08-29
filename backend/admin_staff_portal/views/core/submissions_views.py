from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, F, Case, When, Value, IntegerField
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages

from accounts.decorators import admin, role_required
from submissions.models import Requirement, DocumentSubmission
from submissions.forms import RequirementForm

User = get_user_model()

# Submission Bin Views
@admin
@require_http_methods(['GET', 'POST'])
def add_requirement(request):
    if request.method == 'POST':
        form = RequirementForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('admin_staff_portal:requirements_list')
    else:
        form = RequirementForm()
        
    context = {'form': form}
        
    return render(
        request, 
        'admin_staff_portal/core/submissions/submission_bin/requirement_forms.html', 
        context
    )

@admin
@require_http_methods(['GET', 'POST'])
def edit_requirement(request, requirement_id):
    requirement = get_object_or_404(Requirement, pk=requirement_id)

    if request.method == 'POST':
        form = RequirementForm(request.POST, instance=requirement)
        if form.is_valid():
            form.save()
            return redirect('admin_staff_portal:requirements_list')
    else:
        form = RequirementForm(instance=requirement)
        
    context = {'form': form, 'requirement': requirement}

    return render(
        request, 
        'admin_staff_portal/core/submissions/submission_bin/requirement_forms.html', 
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def requirements_list(request):
    requirements = Requirement.objects.all().order_by('-deadline')

    query = request.GET.get('q')
    category = request.GET.get('category')
    assigned_to = request.GET.get('assigned_to')
    academic_term = request.GET.get('academic_term')

    if query:
        requirements = requirements.filter(requirement_title__icontains=query)
    if category:
        requirements = requirements.filter(category=category)
    if assigned_to:
        requirements = requirements.filter(assigned_to=assigned_to)
    if academic_term:
        requirements = requirements.filter(academic_term=academic_term)

    paginator = Paginator(requirements, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'requirements': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Requirement.objects.values_list('category', flat=True).distinct(),
        'assigned_to_choices': [
            c for c in Requirement.AssignedFacultyType.choices if c[0] != 'ALL'
        ],
        'academic_terms': Requirement.objects.values_list('academic_term', flat=True).distinct(),
    }

    return render(
        request,
        'admin_staff_portal/core/submissions/submission_bin/requirements_list.html',
        context
    )

@admin
@require_http_methods(['POST'])
def toggle_requirement_status(request, requirement_id):
    requirement = get_object_or_404(Requirement, pk=requirement_id)
    
    requirement.status = (
        Requirement.ReqStatus.INACTIVE
        if requirement.status == Requirement.ReqStatus.ACTIVE
        else Requirement.ReqStatus.ACTIVE
    )
    
    requirement.save()
    
    return redirect('admin_staff_portal:requirements_list')

# Faculty Submission Views
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def faculty_submissions_list(request):
    submissions = DocumentSubmission.objects.filter(
        requirement__status=Requirement.ReqStatus.ACTIVE,
        faculty__role=User.Role.FACULTY,
    ).select_related('faculty', 'requirement').order_by(
        '-initially_submitted_at'
    )

    query = request.GET.get('q')
    faculty_type = request.GET.get('faculty_type')
    category = request.GET.get('category')
    review_stage = request.GET.get('review_stage')
    status = request.GET.get('status')

    if query:
        submissions = submissions.filter(
            Q(faculty__first_name__icontains=query) |
            Q(faculty__last_name__icontains=query) |
            Q(requirement__requirement_title__icontains=query)
        )
    if faculty_type:
        submissions = submissions.filter(faculty__faculty_type=faculty_type)
    if category:
        submissions = submissions.filter(requirement__category=category)
    if review_stage:
        submissions = submissions.filter(status=review_stage)
    if status:
        submissions = submissions.filter(status=status)

    paginator = Paginator(submissions, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'faculty_type_choices': [
            c for c in Requirement.AssignedFacultyType.choices if c[0] != 'ALL'
        ],
        'categories': Requirement.objects.values_list('category', flat=True).distinct(),
        'review_stage_choices': DocumentSubmission.SubmissionStatus.choices,
        'status_choices': DocumentSubmission.SubmissionStatus.choices,
    }

    return render(
        request,
        'admin_staff_portal/core/submissions/faculty_submission/faculty_list.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def faculty_submission_bins_view(request, faculty_id):
    faculty_member = get_object_or_404(
        User, 
        pk=faculty_id, 
        role=User.Role.FACULTY
    )
    
    submissions = DocumentSubmission.objects.filter(
        faculty=faculty_member,
        requirement__status=Requirement.ReqStatus.ACTIVE
    ).select_related('requirement').order_by('-requirement__deadline')
    
    category = request.GET.get('category')
    submission_status = request.GET.get('status')
    
    if category:
        submissions = submissions.filter(requirement__category=category)
    if submission_status:
        submissions = submissions.filter(status=submission_status)
        
    paginator = Paginator(submissions, 7)
    page_obj = paginator.get_page(request.GET.get('page'))
        
    all_faculty_submissions = DocumentSubmission.objects.filter(faculty=faculty_member)
    not_ready_count = all_faculty_submissions.exclude(
        status__in=[
            DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
            DocumentSubmission.SubmissionStatus.APPROVED,
        ]
    ).count()
    pending_approval_count = all_faculty_submissions.filter(
        status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    ).count()
    can_approve_all = not_ready_count == 0 and pending_approval_count > 0

    context = {
        'faculty_member': faculty_member,
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'categories': Requirement.objects.values_list('category', flat=True).distinct(),
        'status_choices': DocumentSubmission.SubmissionStatus.choices,
        'can_approve_all': can_approve_all,
        'pending_approval_count': pending_approval_count,
        'not_ready_count': not_ready_count,
    }
    
    return render(
        request,
        'admin_staff_portal/core/submissions/faculty_submission/faculty_submission_bins.html',
        context
    )
    
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def review_submission(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission.objects.select_related(
            'requirement', 'faculty'
        ).prefetch_related(
            'revisions__reviews'),
        pk=submission_id
    )
    
    context = {'submission': submission}
    
    return render(
        request,
        'admin_staff_portal/core/submissions/faculty_submission/review_submission.html',
        context
    )
    
@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def mark_under_review_view(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission,
        pk=submission_id,
        status__in=[
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED
        ]
    )
    
    submission.status = DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    submission.save(update_fields=['status'])
    
    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def mark_reviewed_view(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission,
        pk=submission_id,
        status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    )
    
    update_fields = ['status', 'reviewed_by', 'reviewed_at']
    submission.status = DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    submission.reviewed_by = request.user
    submission.reviewed_at = timezone.now()
    submission.save(update_fields=update_fields)
    
    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

@admin
@require_http_methods(['POST'])
def approve_all_submissions_view(request, faculty_id):
    faculty_member = get_object_or_404(
        User,
        pk=faculty_id,
        role=User.Role.FACULTY
    )

    submissions_qs = DocumentSubmission.objects.filter(faculty=faculty_member)

    not_ready = submissions_qs.exclude(
        status__in=[
            DocumentSubmission.SubmissionStatus.PENDING_APPROVAL,
            DocumentSubmission.SubmissionStatus.APPROVED,
        ]
    ).exists()

    if not_ready:
        messages.error(
            request,
            'All documents must be reviewed and pending approval before you can approve them all.'
        )
        return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)

    now = timezone.now()
    approved_count = submissions_qs.filter(
        status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    ).update(
        status=DocumentSubmission.SubmissionStatus.APPROVED,
        approved_by=request.user,
        approved_at=now,
    )

    messages.success(request, f'{approved_count} document(s) approved.')
    return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)
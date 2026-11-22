from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q, Subquery
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.urls import reverse

from accounts.decorators import access_required
from admin_staff_portal.realtime import refresh_admin_dashboard
from admin_staff_portal.realtime import refresh_staff_dashboard
from admin_staff_portal.realtime import refresh_submission_pages
from notifications.services import build_approval_email, notify_user
from notifications.models import NotificationPreference
from submissions.models import DocumentSubmission, DocumentRevision, active_q
from role_management.models import Role
from accounts.models import FacultyProfile
from admin_staff_portal.helpers.submissions import get_active_submissions
from submissions.forms import DocumentReviewForm
from django.db.models.functions import Coalesce

from submissions.helpers import (
    COMPLIANCE_CHOICES,
    annotate_upload_progress,
    get_target_faculty_queryset
)

from faculty_portal.realtime import (
    refresh_faculty_dashboard,
    refresh_faculty_submission_bin,
    refresh_faculty_my_submissions
)

TEMPLATE_DIR = 'admin_staff_portal/core/submissions/faculty_submission'

TITLE_RELATED = ('requirement__period', 'slot__course', 'slot__program')

User = get_user_model()


@access_required('access_faculty_submissions')
@require_http_methods(['GET'])
def faculty_submissions_list(request):
    query = request.GET.get('q', '').strip()
    faculty_type = request.GET.get('faculty_type', '').strip()
    completion = request.GET.get('completion', '').strip()
    status = request.GET.get('status', '').strip()
    
    if faculty_type not in FacultyProfile.FacultyType.values:
        faculty_type = ''

    if completion not in dict(COMPLIANCE_CHOICES):
        completion = ''

    if status not in DocumentSubmission.SubmissionStatus.values:
        status = ''

    active_submissions = get_active_submissions()

    latest_submission_date = (
        active_submissions
        .filter(faculty=OuterRef('pk'))
        .annotate(
            latest_activity=Coalesce(
                'resubmitted_at',
                'initially_submitted_at'
            )
        )
        .order_by('-latest_activity')
        .values('latest_activity')[:1]
    )

    faculty_members = (
        annotate_upload_progress(get_target_faculty_queryset())
        .select_related('faculty_profile')
        .annotate(latest_submitted_at=Subquery(latest_submission_date))
        .order_by('last_name', 'first_name')
    )

    if query:
        matching_documents = get_active_submissions().filter(requirement__requirement_title__icontains=query)
        faculty_members = faculty_members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(pk__in=matching_documents.values('faculty'))
        )
    if faculty_type:
        faculty_members = faculty_members.filter(faculty_profile__faculty_type=faculty_type)
    if completion:
        faculty_members = faculty_members.filter(compliance_status=completion)
    if status:
        faculty_members = faculty_members.filter(pk__in=active_submissions.filter(status=status).values('faculty'))

    page_obj = Paginator(faculty_members, 7).get_page(request.GET.get('page'))

    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'faculty_type_choices': FacultyProfile.FacultyType.choices,
        'completion_choices': COMPLIANCE_CHOICES,
        'status_choices': DocumentSubmission.SubmissionStatus.choices
    }

    return render(request, f'{TEMPLATE_DIR}/faculty_list.html', context)


@access_required('access_faculty_submissions')
@require_http_methods(['GET'])
def faculty_submission_bins_view(request, faculty_id):
    faculty_member = get_object_or_404(
        User, 
        pk=faculty_id, 
        role__code=Role.Code.FACULTY,
        role__is_default=True
    )

    all_submissions = get_active_submissions().filter(faculty=faculty_member)

    submissions = all_submissions.select_related(*TITLE_RELATED, 'reviewed_by').order_by(
        '-requirement__period__deadline',
        'requirement__order',
        'slot__course__code',
        'slot__year_level',
        'slot__section'
    )

    submission_status = request.GET.get('status')

    if submission_status:
        submissions = submissions.filter(status=submission_status)

    page_obj = Paginator(submissions, 7).get_page(request.GET.get('page'))

    status = DocumentSubmission.SubmissionStatus
    counts = all_submissions.aggregate(
        pending_approval=Count('id', filter=Q(status=status.PENDING_APPROVAL)),
        not_ready=Count('id', filter=~Q(status__in=[status.PENDING_APPROVAL, status.APPROVED]))
    )
    
    not_ready_count = counts['not_ready']
    pending_approval_count = counts['pending_approval']
    can_approve_all = (
        request.user.has_perm('accounts.approve_submissions')
        and not_ready_count == 0
        and pending_approval_count > 0
    )

    context = {
        'faculty_member': faculty_member,
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status_choices': DocumentSubmission.SubmissionStatus.choices,
        'can_approve_all': can_approve_all,
        'pending_approval_count': pending_approval_count,
        'not_ready_count': not_ready_count
    }
    
    return render(request, f'{TEMPLATE_DIR}/faculty_submission_bins.html', context)
    
    
@access_required('access_faculty_submissions')
@require_http_methods(['GET'])
def review_submission(request, submission_id):
    submission = get_object_or_404(
        get_active_submissions().select_related(*TITLE_RELATED, 'faculty', 'reviewed_by', 'approved_by'),
        pk=submission_id
    )
    
    context = {
        'submission': submission,
        'can_review_submissions': request.user.has_perm('accounts.review_faculty_submissions'),
        'can_return_for_revisions': request.user.has_perm('accounts.return_for_revisions'),
    }
    
    return render(request, f'{TEMPLATE_DIR}/review_submission.html', context)
    
    
@access_required('access_faculty_submissions', 'review_faculty_submissions')
@require_http_methods(['POST'])
def mark_under_review_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(get_active_submissions().select_for_update(), pk=submission_id)

        if submission.status not in (
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED
        ):
            messages.info(request, 'This submission was already updated by someone else.')
            
            return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

        submission.status = DocumentSubmission.SubmissionStatus.UNDER_REVIEW
        submission.save(update_fields=['status'])

        transaction.on_commit(
            lambda: (
                refresh_admin_dashboard(),
                refresh_staff_dashboard(),
                refresh_submission_pages({'submission_id': str(submission.id)}),
                refresh_faculty_dashboard(submission.faculty),
                refresh_faculty_my_submissions(submission.faculty),
                notify_user(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_UNDER_REVIEW,
                    title='Document Submission Under Review',
                    message=(
                        f'Your submission for {submission.requirement.requirement_title} '
                        f'is now under review.'
                    ),
                    link=reverse('faculty_portal:view_my_submitted_document', args=[submission.id]),
                )
            )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)


@access_required('access_faculty_submissions', 'review_faculty_submissions')
@require_http_methods(['POST'])
def mark_reviewed_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(get_active_submissions().select_for_update(), pk=submission_id)

        if submission.status != DocumentSubmission.SubmissionStatus.UNDER_REVIEW:
            messages.info(request, 'This submission was already updated by someone else.')
            
            return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

        submission.status = DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        transaction.on_commit(
            lambda: (
                refresh_admin_dashboard(),
                refresh_staff_dashboard(),
                refresh_submission_pages({'submission_id': str(submission.id)}),
                refresh_faculty_dashboard(submission.faculty),
                refresh_faculty_my_submissions(submission.faculty),
                notify_user(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_REVIEWED,
                    title='Document Submission Reviewed',
                    message=(
                        f'Your submission for {submission.requirement.requirement_title} '
                        f'has been reviewed and is now pending approval.'
                    ),
                    link=reverse('faculty_portal:view_my_submitted_document', args=[submission.id]),
                )
            )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)


@access_required('access_faculty_submissions', 'review_faculty_submissions', 'return_for_revisions')
@require_http_methods(['POST'])
def mark_needs_revision_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(get_active_submissions().select_for_update(),pk=submission_id)

        if submission.status != DocumentSubmission.SubmissionStatus.UNDER_REVIEW:
            messages.info(request, 'This submission was already updated by someone else.')
            
            return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

        last_version = submission.revisions.order_by('-version_number').values_list(
            'version_number',
            flat=True
        ).first()
        
        latest_revision = DocumentRevision.objects.create(
            submission=submission,
            version_number=(last_version or 0) + 1
        )
        
        form = DocumentReviewForm(
            request.POST,
            reviewer=request.user,
            revision=latest_revision
        )

        if not form.is_valid() or not form.cleaned_data.get('remarks'):
            messages.error(request, 'Please provide remarks explaining what needs revision.')
            latest_revision.delete()
            
            return redirect('admin_staff_portal:review_submission', submission_id=submission_id)

        form.save()
        submission.status = DocumentSubmission.SubmissionStatus.NEEDS_REVISION
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        transaction.on_commit(
            lambda: (
                refresh_admin_dashboard(),
                refresh_staff_dashboard(),
                refresh_submission_pages({'submission_id': str(submission.id)}),
                refresh_faculty_dashboard(submission.faculty),
                refresh_faculty_submission_bin(submission.faculty),
                refresh_faculty_my_submissions(submission.faculty),
                notify_user(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_NEEDS_REVISION,
                    title='Document Submission Needs Revision',
                    message=(
                        f'Your submission for {submission.requirement.requirement_title} '
                        f'needs revision. Please check the remarks provided by the reviewer.'
                    ),
                    link=reverse('faculty_portal:view_my_submitted_document', args=[submission.id])
                )
            )
        )

    messages.success(request, 'Submission marked as needing revision.')

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)


@access_required('access_faculty_submissions', 'approve_submissions')
@require_http_methods(['POST'])
def approve_selected_submissions_view(request, faculty_id):
    faculty_member = get_object_or_404(
        User,
        pk=faculty_id,
        role__code=Role.Code.FACULTY,
        role__is_default=True
    )

    selected_ids = set()
    invalid_selection = False
    for value in request.POST.getlist('submission_ids'):
        try:
            selected_ids.add(UUID(value))
        except ValueError:
            invalid_selection = True

    if invalid_selection:
        messages.error(
            request,
            'Some selected documents are no longer available. Please refresh the page and try again.',
        )
        
        return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)

    if not selected_ids:
        messages.error(request, 'Please select at least one document to approve.')
        
        return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)

    pending_status = DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    approved_status = DocumentSubmission.SubmissionStatus.APPROVED
    approval_time = timezone.now()

    with transaction.atomic():
        eligible_ids = list(
            DocumentSubmission.objects
            .select_for_update()
            .filter(
                active_q('requirement__'),
                pk__in=selected_ids,
                faculty=faculty_member,
                status=pending_status
            )
            .values_list('pk', flat=True)
        )

        if not eligible_ids:
            messages.error(
                request,
                'None of the selected documents are currently marked as reviewed/pending approval.',
            )
            
            return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)

        approved_count = DocumentSubmission.objects.filter(
            active_q('requirement__'),
            pk__in=eligible_ids,
            faculty=faculty_member,
            status=pending_status
        ).update(
            status=approved_status,
            approved_by=request.user,
            approved_at=approval_time
        )

        if approved_count:
            def publish_approval_updates():
                refresh_admin_dashboard()
                refresh_staff_dashboard()
                refresh_submission_pages({'faculty_id': str(faculty_member.id)})
                refresh_faculty_dashboard(faculty_member)
                refresh_faculty_submission_bin(faculty_member)
                refresh_faculty_my_submissions(faculty_member)

                approved_submissions = (
                    DocumentSubmission.objects
                    .filter(pk__in=eligible_ids)
                    .select_related(*TITLE_RELATED)
                )
                
                email_subject, email_message = build_approval_email(
                    recipient=faculty_member,
                    document_names=(
                        submission.full_title
                        for submission in approved_submissions
                    ),
                    approved_by=request.user,
                    approved_at=approval_time,
                )

                notify_user(
                    user=faculty_member,
                    notification_type=(
                        NotificationPreference.NotificationType.SUBMISSION_APPROVED
                    ),
                    title='Selected Document Submissions Approved',
                    message=(
                        f'{approved_count} selected document(s) have been approved.'
                    ),
                    link=reverse('faculty_portal:my_submissions'),
                    email_subject=email_subject,
                    email_message=email_message
                )

            transaction.on_commit(publish_approval_updates)

    if approved_count:
        messages.success(
            request,
            f'{approved_count} selected document(s) approved successfully.'
        )
    else:
        messages.error(
            request,
            'No selected documents were approved. Please refresh and try again.'
        )

    return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)

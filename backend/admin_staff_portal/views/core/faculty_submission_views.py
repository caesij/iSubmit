from uuid import UUID

from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.urls import reverse

from accounts.decorators import admin, role_required, staff_permission_required
from admin_staff_portal.realtime import refresh_admin_dashboard
from admin_staff_portal.realtime import refresh_staff_dashboard
from admin_staff_portal.realtime import refresh_submission_pages
from notifications.services import create_notif
from notifications.models import NotificationPreference
from submissions.models import DocumentSubmission, DocumentRevision, Requirement
from submissions.forms import DocumentReviewForm
from accounts.models import StaffPermission

from faculty_portal.realtime import (
    refresh_faculty_dashboard,
    refresh_faculty_submission_bin,
    refresh_faculty_my_submissions,
)

User = get_user_model()


# Faculty Submission Views
@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def faculty_submissions_list(request):
    query = request.GET.get('q')
    faculty_type = request.GET.get('faculty_type')
    category = request.GET.get('category')
    status = request.GET.get('status')

    faculty_members = User.objects.filter(
        role=User.Role.FACULTY,
        is_active=True,
    ).order_by('last_name', 'first_name')

    if query:
        faculty_members = faculty_members.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(submissions__requirement__requirement_title__icontains=query)
        )
    if faculty_type:
        faculty_members = faculty_members.filter(faculty_type=faculty_type)

    faculty_rows = []
    active_requirements = Requirement.objects.filter(status=Requirement.ReqStatus.ACTIVE)
    for faculty_member in faculty_members.distinct():
        assigned_requirements = active_requirements.filter(
            Q(assigned_to=Requirement.AssignedFacultyType.ALL)
            | Q(assigned_to=faculty_member.faculty_type)
        )
        faculty_submissions = DocumentSubmission.objects.filter(
            faculty=faculty_member,
            requirement__status=Requirement.ReqStatus.ACTIVE,
        ).select_related('requirement').order_by('-initially_submitted_at')
        total_count = assigned_requirements.count()
        submitted_count = faculty_submissions.values('requirement_id').distinct().count()
        approved_count = faculty_submissions.filter(
            status=DocumentSubmission.SubmissionStatus.APPROVED
        ).values('requirement_id').distinct().count()

        if category:
            faculty_submissions = faculty_submissions.filter(
                requirement__category=category
            )
        if status:
            faculty_submissions = faculty_submissions.filter(status=status)

        latest_submission = faculty_submissions.first()
        faculty_rows.append({
            'faculty': faculty_member,
            'submitted_count': faculty_submissions.count(),
            'total_count': total_count,
            'compliance_status': (
                'approved'
                if total_count and approved_count == total_count
                else 'complete'
                if total_count and submitted_count == total_count
                else 'incomplete'
            ),
            'latest_submission': latest_submission,
        })

    paginator = Paginator(faculty_rows, 7)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'submissions': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'faculty_type_choices': [
            c for c in Requirement.AssignedFacultyType.choices if c[0] != 'ALL'
        ],
        'categories': Requirement.objects.values_list('category', flat=True).distinct(),
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
            DocumentSubmission.SubmissionStatus.APPROVED
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
        'not_ready_count': not_ready_count
    }
    
    return render(
        request,
        'admin_staff_portal/core/submissions/faculty_submission/faculty_submission_bins.html',
        context
    )
    
    
@role_required('ADMIN', 'STAFF')
@staff_permission_required('review_faculty_submissions')
@require_http_methods(['GET'])
def review_submission(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission.objects.select_related('requirement', 'faculty').prefetch_related('revisions__reviews'),
        pk=submission_id
    )
    
    context = {
        'submission': submission,
        'can_return_for_revisions': (
            request.user.is_admin
            or StaffPermission.get_solo().is_effectively_enabled('return_for_revisions')
        ),
    }
    
    return render(
        request,
        'admin_staff_portal/core/submissions/faculty_submission/review_submission.html',
        context
    )
    
    
@role_required('ADMIN', 'STAFF')
@staff_permission_required('review_faculty_submissions')
@require_http_methods(['POST'])
def mark_under_review_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(
            DocumentSubmission.objects.select_for_update(),
            pk=submission_id,
        )

        if submission.status not in (
            DocumentSubmission.SubmissionStatus.SUBMITTED,
            DocumentSubmission.SubmissionStatus.RESUBMITTED,
        ):
            messages.info(request, 'This submission was already updated by someone else.')
            return redirect(
                'admin_staff_portal:review_submission',
                submission_id=submission.id,
            )

        submission.status = DocumentSubmission.SubmissionStatus.UNDER_REVIEW
        submission.save(update_fields=['status'])

        transaction.on_commit(
            lambda: (
                refresh_admin_dashboard(),
                refresh_staff_dashboard(),
                refresh_submission_pages({'submission_id': str(submission.id)}),
                refresh_faculty_dashboard(submission.faculty),
                refresh_faculty_my_submissions(submission.faculty),
                create_notif(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_NOTIFICATIONS,
                    title='Document Submission Under Review',
                    message=(
                        f'Your submission for {submission.requirement.requirement_title} '
                        f'is now under review.'
                    ),
                    link=reverse('faculty_portal:view_my_submitted_document', args=[submission.id])
                )
            )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)


@role_required('ADMIN', 'STAFF')
@staff_permission_required('review_faculty_submissions')
@require_http_methods(['POST'])
def mark_reviewed_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(
            DocumentSubmission.objects.select_for_update(),
            pk=submission_id,
        )

        if submission.status != DocumentSubmission.SubmissionStatus.UNDER_REVIEW:
            messages.info(request, 'This submission was already updated by someone else.')
            return redirect(
                'admin_staff_portal:review_submission',
                submission_id=submission.id,
            )

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
                create_notif(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_NOTIFICATIONS,
                    title='Document Submission Reviewed',
                    message=(
                        f'Your submission for {submission.requirement.requirement_title} '
                        f'has been reviewed and is now pending approval.'
                    ),
                    link=reverse('faculty_portal:view_my_submitted_document', args=[submission.id])
                )
            )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)


@role_required('ADMIN', 'STAFF')
@staff_permission_required('return_for_revisions')
@require_http_methods(['POST'])
def mark_needs_revision_view(request, submission_id):
    with transaction.atomic():
        submission = get_object_or_404(
            DocumentSubmission.objects.select_for_update(),
            pk=submission_id,
        )

        if submission.status != DocumentSubmission.SubmissionStatus.UNDER_REVIEW:
            messages.info(request, 'This submission was already updated by someone else.')
            return redirect(
                'admin_staff_portal:review_submission',
                submission_id=submission.id,
            )

        last_version = submission.revisions.order_by('-version_number').values_list(
            'version_number',
            flat=True,
        ).first()
        latest_revision = DocumentRevision.objects.create(
            submission=submission,
            version_number=(last_version or 0) + 1,
        )
        form = DocumentReviewForm(
            request.POST,
            reviewer=request.user,
            revision=latest_revision,
        )

        if not form.is_valid() or not form.cleaned_data.get('remarks'):
            messages.error(request, 'Please provide remarks explaining what needs revision.')
            latest_revision.delete()
            return redirect(
                'admin_staff_portal:review_submission',
                submission_id=submission_id,
            )

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
                create_notif(
                    user=submission.faculty,
                    notification_type=NotificationPreference.NotificationType.SUBMISSION_NOTIFICATIONS,
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


@admin
@require_http_methods(['POST'])
def approve_selected_submissions_view(request, faculty_id):
    faculty_member = get_object_or_404(
        User,
        pk=faculty_id,
        role=User.Role.FACULTY
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
            'The selected document IDs are invalid. Please refresh the page and try again.',
        )
        return redirect(
            'admin_staff_portal:faculty_submission_bins_view',
            faculty_id=faculty_member.id
        )

    if not selected_ids:
        messages.error(
            request,
            'Please select at least one document to approve.',
        )
        return redirect(
            'admin_staff_portal:faculty_submission_bins_view',
            faculty_id=faculty_member.id
        )

    pending_status = DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
    approved_status = DocumentSubmission.SubmissionStatus.APPROVED

    with transaction.atomic():
        eligible_ids = list(
            DocumentSubmission.objects
            .select_for_update()
            .filter(
                pk__in=selected_ids,
                faculty=faculty_member,
                requirement__status=Requirement.ReqStatus.ACTIVE,
                status=pending_status
            )
            .values_list('pk', flat=True)
        )

        if not eligible_ids:
            messages.error(
                request,
                'None of the selected documents are currently marked as reviewed/pending approval.',
            )
            return redirect(
                'admin_staff_portal:faculty_submission_bins_view',
                faculty_id=faculty_member.id,
            )

        approved_count = DocumentSubmission.objects.filter(
            pk__in=eligible_ids,
            faculty=faculty_member,
            requirement__status=Requirement.ReqStatus.ACTIVE,
            status=pending_status
        ).update(
            status=approved_status,
            approved_by=request.user,
            approved_at=timezone.now()
        )

        if approved_count:
            def publish_approval_updates():
                refresh_admin_dashboard()
                refresh_staff_dashboard()
                refresh_submission_pages({'faculty_id': str(faculty_member.id)})
                refresh_faculty_dashboard(faculty_member)
                refresh_faculty_submission_bin(faculty_member)
                refresh_faculty_my_submissions(faculty_member)

                create_notif(
                    user=faculty_member,
                    notification_type=(
                        NotificationPreference.NotificationType.SUBMISSION_NOTIFICATIONS
                    ),
                    title='Selected Document Submissions Approved',
                    message=(f'{approved_count} selected document(s) have been approved.'),
                    link=reverse('faculty_portal:my_submissions')
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

    return redirect(
        'admin_staff_portal:faculty_submission_bins_view',
        faculty_id=faculty_member.id
    )
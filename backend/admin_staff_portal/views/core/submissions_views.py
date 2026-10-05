from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.formats import date_format

from accounts.decorators import admin, role_required, staff_permission_required
from admin_staff_portal.realtime import refresh_admin_dashboard
from admin_staff_portal.realtime import refresh_staff_dashboard
from admin_staff_portal.helpers.submissions import refresh_requirement_faculty_dashboards
from notifications.services import create_notif
from notifications.models import NotificationPreference

from faculty_portal.realtime import (
    refresh_faculty_dashboard,
    refresh_faculty_submission_bin,
    refresh_all_faculty_submission_bins,
    refresh_faculty_my_submissions,
)

from submissions.models import (
    Requirement,
    DocumentSubmission,
    DocumentRevision,
)

from submissions.forms import (
    RequirementForm,
    DocumentReviewForm,
)

from accounts.models import StaffPermission

User = get_user_model()

# Submission Bin Views
@role_required('ADMIN', 'STAFF')
@staff_permission_required('create_submission_bins')
@require_http_methods(['GET'])
def bulk_requirements_view(request):
    bulk_requirements = request.session.get('bulk_requirements', [])

    display_requirements = []

    assigned_labels = dict(Requirement.AssignedFacultyType.choices)
    semester_labels = dict(Requirement.Semester.choices)
    status_labels = dict(Requirement.ReqStatus.choices)

    for index, item in enumerate(bulk_requirements):
        display_item = item.copy()

        deadline = parse_datetime(item.get('deadline', ''))

        if deadline:
            display_item['deadline_date'] = date_format(deadline, 'F j, Y')
            display_item['deadline_time'] = date_format(deadline, 'g:i A')
        else:
            display_item['deadline_date'] = ''
            display_item['deadline_time'] = ''

        display_item['assigned_to_display'] = (
            assigned_labels.get(
                item.get('assigned_to'),
                item.get('assigned_to', '')
            )
        )

        display_item['semester_display'] = (
            semester_labels.get(
                item.get('semester'),
                item.get('semester', '')
            )
        )

        display_item['status_display'] = (
            status_labels.get(
                item.get('status'),
                item.get('status', '')
            )
        )

        display_item['index'] = index

        display_requirements.append(display_item)

    context = {'bulk_requirements': display_requirements,}

    return render(
        request,
        'admin_staff_portal/core/submissions/submission_bin/bulk_requirements.html',
        context
    )


@role_required('ADMIN', 'STAFF')
@staff_permission_required('create_submission_bins')
@require_http_methods(['GET', 'POST'])
def add_requirement_to_bulk(request):
    if request.method == 'POST':
        form = RequirementForm(request.POST)

        if form.is_valid():
            bulk_requirements = request.session.get('bulk_requirements', [])

            requirement_title = (form.cleaned_data['requirement_title'])
            academic_year = (form.cleaned_data['academic_year'])
            semester = (form.cleaned_data['semester'])

            staged_key = (
                requirement_title.casefold(),
                academic_year,
                semester
            )

            existing_keys = {
                (
                    item['requirement_title'].casefold(),
                    item['academic_year'],
                    item['semester'],
                )
                for item in bulk_requirements
            }

            if staged_key in existing_keys:
                form.add_error(
                    'requirement_title',
                    'This requirement is already in the current list.'
                )
            else:
                deadline = form.cleaned_data['deadline']

                bulk_requirements.append({
                    'requirement_title': requirement_title,
                    'category': form.cleaned_data['category'],
                    'assigned_to': form.cleaned_data['assigned_to'],
                    'academic_year': academic_year,
                    'semester': semester,
                    'status': form.cleaned_data['status'],
                    'deadline': deadline.strftime('%Y-%m-%dT%H:%M'),
                    'ocr_enabled':form.cleaned_data['ocr_enabled']
                })

                request.session['bulk_requirements'] = (bulk_requirements)
                request.session.modified = True

                return redirect('admin_staff_portal:bulk_requirements')
    else:
        form = RequirementForm()

    context = {'form': form}

    return render(
        request,
        'admin_staff_portal/core/submissions/submission_bin/requirement_forms.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@staff_permission_required('create_submission_bins')
@require_http_methods(['POST'])
def delete_bulk_requirement(request, index):
    bulk_requirements = request.session.get('bulk_requirements', [])

    if 0 <= index < len(bulk_requirements):
        bulk_requirements.pop(index)
        request.session['bulk_requirements'] = bulk_requirements
        request.session.modified = True

    return redirect('admin_staff_portal:bulk_requirements')


@role_required('ADMIN', 'STAFF')
@staff_permission_required('create_submission_bins')
@require_http_methods(['POST'])
def post_bulk_requirements(request):
    bulk_requirements = request.session.get('bulk_requirements', [])

    if not bulk_requirements:
        messages.error(request, 'There are no requirements to post.')
        return redirect('admin_staff_portal:bulk_requirements')

    try:
        with transaction.atomic():
            created_requirements = []

            for item in bulk_requirements:
                form = RequirementForm(data={
                    'requirement_title': item['requirement_title'],
                    'category': item['category'],
                    'assigned_to': item['assigned_to'],
                    'academic_year': item['academic_year'],
                    'semester': item['semester'],
                    'status': item['status'],
                    'deadline': item['deadline'],
                    'ocr_enabled': item['ocr_enabled'],
                })

                if not form.is_valid():
                    raise ValueError('One or more staged requirements are invalid.')

                requirement = form.save()
                created_requirements.append(requirement)

            active_requirements = [
                requirement
                for requirement in created_requirements
                if requirement.status == Requirement.ReqStatus.ACTIVE
            ]

            def publish_bulk_updates():
                try:
                    refresh_admin_dashboard()
                    refresh_staff_dashboard()

                    if not active_requirements:
                        return

                    faculty_users = User.objects.filter(role=User.Role.FACULTY, is_active=True)

                    for faculty_member in faculty_users:
                        matching_requirements = [
                            requirement
                            for requirement in active_requirements
                            if (requirement.assigned_to == Requirement.AssignedFacultyType.ALL
                                or
                                requirement.assigned_to== faculty_member.faculty_type
                            )
                        ]

                        if not matching_requirements:
                            continue

                        refresh_faculty_dashboard(faculty_member)
                        refresh_faculty_submission_bin(faculty_member)

                        titles = '\n'.join(
                            f'• {requirement.requirement_title}'
                            for requirement
                            in matching_requirements
                        )

                        create_notif(
                            user=faculty_member,
                            notification_type=(NotificationPreference.NotificationType.SYSTEM_ANNOUNCEMENT),
                            title='New Submission Requirements',
                            message=(
                                f'{len(matching_requirements)} new '
                                f'submission requirement(s) have been '
                                f'posted:\n\n'
                                f'{titles}'
                            ),
                            link=reverse('faculty_portal:upload_files')
                        )

                except Exception as e:
                    print('BULK REQUIREMENT REALTIME ERROR:', repr(e))

            transaction.on_commit(
                publish_bulk_updates
            )

        request.session.pop('bulk_requirements', None)
        request.session.modified = True

        messages.success(
            request,
            f'{len(created_requirements)} requirement(s) '
            f'posted successfully.'
        )

        return redirect('admin_staff_portal:requirements_list')

    except Exception as e:
        print('BULK REQUIREMENT ERROR:', repr(e))

        messages.error(
            request,
            f'An error occurred while posting the requirements. '
            f'Please review the staged requirements and try again.'
        )

        return redirect('admin_staff_portal:bulk_requirements')

@role_required('ADMIN', 'STAFF')
@staff_permission_required('edit_submission_bin')
@require_http_methods(['GET', 'POST'])
def edit_requirement(request, requirement_id):
    requirement = get_object_or_404(Requirement, pk=requirement_id)

    if request.method == 'POST':
        old_assigned_to = requirement.assigned_to

        form = RequirementForm(request.POST, instance=requirement)

        if form.is_valid():
            requirement = form.save()

            refresh_admin_dashboard()
            refresh_staff_dashboard()
            refresh_all_faculty_submission_bins()

            refresh_requirement_faculty_dashboards(old_assigned_to, requirement.assigned_to)

            return redirect('admin_staff_portal:requirements_list')
    else:
        form = RequirementForm(instance=requirement)

    context = {
        'form': form,
        'requirement': requirement,
    }

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
    semester = request.GET.get('semester')
    academic_year = request.GET.get('academic_year')

    if query:
        requirements = requirements.filter(requirement_title__icontains=query)
    if category:
        requirements = requirements.filter(category=category)
    if assigned_to:
        requirements = requirements.filter(assigned_to=assigned_to)
    if semester:
        requirements = requirements.filter(semester=semester)
    if academic_year:
        requirements = requirements.filter(academic_term=f'A.Y. {academic_year}')

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
        'academic_years': [
            term.replace('A.Y. ', '')
            for term in Requirement.objects.values_list('academic_term', flat=True).distinct().order_by('-academic_term')
        ],
    }

    return render(
        request,
        'admin_staff_portal/core/submissions/submission_bin/requirements_list.html',
        context
    )

@role_required('ADMIN', 'STAFF')
@staff_permission_required('edit_submission_bin')
@require_http_methods(['POST'])
def toggle_requirement_status(request, requirement_id):
    requirement = get_object_or_404(
        Requirement,
        pk=requirement_id
    )

    requirement.status = (
        Requirement.ReqStatus.INACTIVE
        if requirement.status == Requirement.ReqStatus.ACTIVE
        else Requirement.ReqStatus.ACTIVE
    )

    requirement.save()
    refresh_all_faculty_submission_bins()

    faculty_qs = User.objects.filter(role=User.Role.FACULTY)

    if requirement.assigned_to != Requirement.AssignedFacultyType.ALL:
        faculty_qs = faculty_qs.filter(faculty_type=requirement.assigned_to)

    for faculty_member in faculty_qs:
        refresh_faculty_dashboard(faculty_member)

    messages.success(request, 'Requirement status updated.')

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
    submission = get_object_or_404(DocumentSubmission, pk=submission_id)

    if submission.status not in (
        DocumentSubmission.SubmissionStatus.SUBMITTED,
        DocumentSubmission.SubmissionStatus.RESUBMITTED,
    ):
        messages.info(request, 'This submission was already updated by someone else.')
        return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

    with transaction.atomic():
        submission.status = DocumentSubmission.SubmissionStatus.UNDER_REVIEW
        submission.save(update_fields=['status'])

        transaction.on_commit(
                lambda: (
                    refresh_admin_dashboard(),
                    refresh_staff_dashboard(),
                    refresh_faculty_dashboard(submission.faculty),
                    refresh_faculty_my_submissions(submission.faculty),
                    
                    create_notif(
                        user=submission.faculty,
                        notification_type=NotificationPreference.NotificationType.SUBMISSION_UPDATES,
                        title='Document Submission Under Review',
                        message=(
                            f'Your submission for {submission.requirement.requirement_title} '
                            f'is now under review.'
                        ),
                        link=''
                    )
                )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

@role_required('ADMIN', 'STAFF')
@staff_permission_required('review_faculty_submissions')
@require_http_methods(['POST'])
def mark_reviewed_view(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission,
        pk=submission_id,
        status=DocumentSubmission.SubmissionStatus.UNDER_REVIEW
    )
    
    with transaction.atomic():
        submission.status = DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
        submission.reviewed_by = request.user
        submission.reviewed_at = timezone.now()
        submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

        transaction.on_commit(
                lambda: (
                    refresh_admin_dashboard(),
                    refresh_staff_dashboard(),
                    refresh_faculty_dashboard(submission.faculty),
                    refresh_faculty_my_submissions(submission.faculty),
                    
                    create_notif(
                        user=submission.faculty,
                        notification_type=NotificationPreference.NotificationType.SUBMISSION_UPDATES,
                        title='Document Submission Reviewed',
                        message=(
                            f'Your submission for {submission.requirement.requirement_title} '
                            f'has been reviewed and is now pending approval.'
                        ),
                        link=''
                    )
                )
        )

    return redirect('admin_staff_portal:review_submission', submission_id=submission.id)

@role_required('ADMIN', 'STAFF')
@staff_permission_required('return_for_revisions')
@require_http_methods(['POST'])
def mark_needs_revision_view(request, submission_id):
    submission = get_object_or_404(
        DocumentSubmission,
        pk=submission_id,
        status__in=[DocumentSubmission.SubmissionStatus.UNDER_REVIEW]
    )

    last_version = (
        submission.revisions
        .order_by('-version_number')
        .values_list('version_number', flat=True)
        .first()
    )

    next_version = (last_version or 0) + 1

    latest_revision = DocumentRevision.objects.create(submission=submission, version_number=next_version)

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

    with transaction.atomic():
            submission.status = (DocumentSubmission.SubmissionStatus.NEEDS_REVISION)
            submission.reviewed_by = request.user
            submission.reviewed_at = timezone.now()
            submission.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])

            transaction.on_commit(
                    lambda: (      
                            refresh_admin_dashboard(),
                            refresh_staff_dashboard(),
                            refresh_faculty_dashboard(submission.faculty),
                            refresh_faculty_submission_bin(submission.faculty),
                            refresh_faculty_my_submissions(submission.faculty),
                            
                        create_notif(
                            user=submission.faculty,
                            notification_type=NotificationPreference.NotificationType.SUBMISSION_UPDATES,
                            title='Document Submission Needs Revision',
                            message=(
                                f'Your submission for {submission.requirement.requirement_title} '
                                f'needs revision. Please check the remarks provided by the reviewer.'
                            ),
                            link=''
                        )
                    )
        )

    messages.success(request, 'Submission marked as needing revision.')

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

    with transaction.atomic():
        approved_count = submissions_qs.filter(
            status=DocumentSubmission.SubmissionStatus.PENDING_APPROVAL
        ).update(
            status=DocumentSubmission.SubmissionStatus.APPROVED,
            approved_by=request.user,
            approved_at=now,
        )
        
        transaction.on_commit(
            lambda: (
                    refresh_staff_dashboard(),
                    refresh_faculty_dashboard(faculty_member),
                    refresh_faculty_my_submissions(faculty_member),
                    
                    create_notif(
                        user=faculty_member,
                        notification_type=NotificationPreference.NotificationType.SUBMISSION_UPDATES,
                        title='All Document Submissions Approved',
                        message=(f'All your document submissions have been approved.'),
                        link=''
                    )
            )
        )

    messages.success(request, f'{approved_count} document(s) approved.')
    return redirect('admin_staff_portal:faculty_submission_bins_view', faculty_id=faculty_member.id)
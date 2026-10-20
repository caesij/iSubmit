from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.utils.dateparse import parse_datetime

from accounts.decorators import role_required, staff_permission_required
from core.date_formatting import format_display_date, format_display_time
from admin_staff_portal.realtime import refresh_admin_dashboard
from admin_staff_portal.realtime import refresh_staff_dashboard
from admin_staff_portal.realtime import refresh_submission_pages
from admin_staff_portal.helpers.submissions import refresh_requirement_faculty_dashboards
from notifications.services import create_notif
from notifications.models import NotificationPreference

from faculty_portal.realtime import (
    refresh_faculty_dashboard,
    refresh_faculty_submission_bin,
    refresh_all_faculty_submission_bins,
)

from submissions.models import Requirement

from submissions.forms import RequirementForm

User = get_user_model()


# Submission Bin Views
@role_required('ADMIN', 'STAFF')
@staff_permission_required('manage_submission_bins')
@require_http_methods(['GET'])
def bulk_requirements_view(request):
    bulk_requirements = request.session.get('bulk_requirements', [])

    display_requirements = []

    assigned_labels = dict(Requirement.AssignedFacultyType.choices)
    semester_labels = dict(Requirement.Semester.choices)
    status_labels = dict(Requirement.ReqStatus.choices)
    processing_mode_labels = dict(Requirement.TextProcessingMode.choices)

    for index, item in enumerate(bulk_requirements):
        display_item = item.copy()

        deadline = parse_datetime(item.get('deadline', ''))

        if deadline:
            display_item['deadline_date'] = format_display_date(deadline, request.user)
            display_item['deadline_time'] = format_display_time(deadline, request.user)
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
        display_item['text_processing_mode'] = item.get(
            'text_processing_mode',
            'OCR' if item.get('ocr_enabled') else 'NONE'
        )
        display_item['text_processing_mode_display'] = processing_mode_labels.get(
            display_item['text_processing_mode'],
            item.get('text_processing_mode', '')
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
@staff_permission_required('manage_submission_bins')
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
                    'text_processing_mode': form.cleaned_data['text_processing_mode'],
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
@staff_permission_required('manage_submission_bins')
@require_http_methods(['POST'])
def delete_bulk_requirement(request, index):
    bulk_requirements = request.session.get('bulk_requirements', [])

    if 0 <= index < len(bulk_requirements):
        bulk_requirements.pop(index)
        request.session['bulk_requirements'] = bulk_requirements
        request.session.modified = True

    return redirect('admin_staff_portal:bulk_requirements')


@role_required('ADMIN', 'STAFF')
@staff_permission_required('manage_submission_bins')
@require_http_methods(['POST'])
def post_bulk_requirements(request):
    bulk_requirements = request.session.get('bulk_requirements', [])

    if not bulk_requirements:
        messages.error(request, 'There are no requirements waiting to be posted.')
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
                    'text_processing_mode': item.get(
                        'text_processing_mode',
                        'OCR' if item.get('ocr_enabled') else 'NONE'
                    ),
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
                    refresh_submission_pages()

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
                            (
                                f"• {requirement.requirement_title} — "
                                f"Deadline: "
                                f"{format_display_date(requirement.deadline, faculty_member)}"
                                if requirement.deadline
                                else f"• {requirement.requirement_title} — No deadline set"
                            )
                            for requirement in matching_requirements
                        )

                        create_notif(
                            user=faculty_member,
                            notification_type=(NotificationPreference.NotificationType.SYSTEM_NOTIFICATIONS),
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

            transaction.on_commit(publish_bulk_updates)

        request.session.pop('bulk_requirements', None)
        request.session.modified = True

        messages.success(
            request,
            f'{len(created_requirements)} requirement(s) posted successfully.'
        )

        return redirect('admin_staff_portal:requirements_list')

    except Exception as e:
        print('BULK REQUIREMENT ERROR:', repr(e))

        messages.error(
            request,
            'We could not post these requirements. Please review the staged entries and try again.'
        )

        return redirect('admin_staff_portal:bulk_requirements')


@role_required('ADMIN', 'STAFF')
@staff_permission_required('manage_submission_bins')
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
            refresh_submission_pages()
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
@staff_permission_required('manage_submission_bins')
@require_http_methods(['POST'])
def toggle_requirement_status(request, requirement_id):
    with transaction.atomic():
        requirement = get_object_or_404(
            Requirement.objects.select_for_update(),
            pk=requirement_id,
        )
        requirement.status = (
            Requirement.ReqStatus.INACTIVE
            if requirement.status == Requirement.ReqStatus.ACTIVE
            else Requirement.ReqStatus.ACTIVE
        )
        requirement.save(update_fields=['status', 'updated_at'])

        faculty_qs = User.objects.filter(role=User.Role.FACULTY)
        if requirement.assigned_to != Requirement.AssignedFacultyType.ALL:
            faculty_qs = faculty_qs.filter(faculty_type=requirement.assigned_to)

        def publish_requirement_updates():
            refresh_admin_dashboard()
            refresh_staff_dashboard()
            refresh_submission_pages({'requirement_id': str(requirement.id)})
            refresh_all_faculty_submission_bins()
            for faculty_member in faculty_qs:
                refresh_faculty_dashboard(faculty_member)

        transaction.on_commit(publish_requirement_updates)

    messages.success(request, 'Requirement status updated.')

    return redirect('admin_staff_portal:requirements_list')

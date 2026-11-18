import secrets
import string

from axes.utils import reset as axes_reset

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from accounts.decorators import role_required
from core.search_utils import all_terms_query
from programs.models import Program
from submissions.models import ClassAssignment

from user_management.forms import (
    UserManagementForm,
    ClassAssignmentFormSet,
)


User = get_user_model()

TEMPLATE_DIR = 'admin_staff_portal/core/user_mgmt'


@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET'])
def user_list_view(request):

    if request.user.is_admin:
        visible_roles = User.Role.values
        manageable_roles = [User.Role.STAFF, User.Role.FACULTY]
    else:
        visible_roles = [User.Role.FACULTY]
        manageable_roles = [User.Role.FACULTY]

    selected_role = request.GET.get('role', 'ALL').strip().upper()
    search_query = request.GET.get('q', '').strip()
    faculty_type = request.GET.get('faculty_type', '').strip()
    status = request.GET.get('status', '').strip().lower()
    lockout = request.GET.get('lockout', '').strip().lower()

    if selected_role != 'ALL' and selected_role not in visible_roles:
        selected_role = 'ALL'

    if faculty_type not in User.FacultyType.values:
        faculty_type = ''

    if status not in ('active', 'inactive'):
        status = ''

    if lockout not in ('locked', 'unlocked'):
        lockout = ''

    users = User.objects.filter(
        role__in=visible_roles
    ).prefetch_related('assigned_programs')

    if selected_role != 'ALL':
        users = users.filter(role=selected_role)

    if search_query:
        users = users.filter(
            all_terms_query(
                search_query,
                'first_name',
                'middle_name',
                'last_name',
                'email'
            )
        )

    if faculty_type and selected_role in ('ALL', User.Role.FACULTY):
        users = users.filter(
            role=User.Role.FACULTY,
            faculty_type=faculty_type
        )

    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)

    if lockout == 'locked':
        users = users.filter(is_locked_out=True)
    elif lockout == 'unlocked':
        users = users.filter(is_locked_out=False)

    users = users.order_by('last_name', 'first_name', 'pk')

    page_obj = Paginator(users, 7).get_page(
        request.GET.get('page')
    )

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)
    pagination_params['role'] = selected_role

    if selected_role not in ('ALL', User.Role.FACULTY):
        pagination_params.pop('faculty_type', None)

    role_choices = [
        ('ALL', 'All Roles')
    ] + [
        (value, label)
        for value, label in User.Role.choices
        if value in visible_roles
    ]

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'pagination_query': pagination_params.urlencode(),

        'page_title': 'User Management',
        'selected_role': selected_role,
        'role_choices': role_choices,
        'manageable_roles': manageable_roles,

        'show_faculty_type': selected_role in ('ALL', User.Role.FACULTY),
        'faculty_type_choices': User.FacultyType.choices,

        'search_query': search_query,
        'faculty_type_param': faculty_type,
        'status_param': status,
        'lockout_param': lockout,
    }

    return render(
        request,
        f'{TEMPLATE_DIR}/user_list.html',
        context
    )


@role_required('ADMIN', 'STAFF')
@require_http_methods(['GET', 'POST'])
def user_form_view(request, pk=None):

    if request.user.is_admin:
        manageable_roles = [User.Role.STAFF, User.Role.FACULTY]
    else:
        manageable_roles = [User.Role.FACULTY]

    if pk:
        target_user = get_object_or_404(
            User,
            pk=pk,
            role__in=manageable_roles
        )
    else:
        target_user = User()

    if request.method == 'POST':
        form = UserManagementForm(
            request.POST,
            instance=target_user,
            request_user=request.user
        )
        form_valid = form.is_valid()

    else:
        initial = {}

        if not pk:
            selected_role = request.GET.get(
                'role',
                User.Role.FACULTY
            ).strip().upper()

            if selected_role not in manageable_roles:
                selected_role = User.Role.FACULTY

            initial['role'] = selected_role

        form = UserManagementForm(
            instance=target_user,
            request_user=request.user,
            initial=initial
        )
        form_valid = False

    # Determine the role currently selected in the form.
    selected_role = form['role'].value()
    show_faculty_fields = selected_role == User.Role.FACULTY

    # Determine which programs are available to the assignment formset.
    if request.method == 'POST':
        if form_valid and show_faculty_fields:
            allowed_programs = form.cleaned_data.get(
                'assigned_programs',
                Program.objects.none()
            )
        elif show_faculty_fields:
            allowed_programs = Program.objects.filter(
                pk__in=request.POST.getlist('assigned_programs')
            )
        else:
            allowed_programs = Program.objects.none()

    elif target_user.pk and show_faculty_fields:
        allowed_programs = target_user.assigned_programs.all()

    else:
        allowed_programs = Program.objects.none()

    # Only load existing assignments that belong to the selected programs.
    if target_user.pk and show_faculty_fields:
        assignment_queryset = (
            ClassAssignment.objects.filter(
                faculty=target_user,
                program__in=allowed_programs
            )
            .select_related('program', 'course')
            .order_by(
                'academic_year',
                'semester',
                'program__program_name',
                'year_level',
                'section',
                'course__code'
            )
        )
    else:
        assignment_queryset = ClassAssignment.objects.none()

    assignment_formset = ClassAssignmentFormSet(
        request.POST if request.method == 'POST' and show_faculty_fields else None,
        instance=target_user,
        queryset=assignment_queryset,
        prefix='assignments',
        form_kwargs={
            'allowed_programs': allowed_programs
        }
    )

    assignment_formset_valid = True

    if request.method == 'POST' and show_faculty_fields:
        assignment_formset_valid = assignment_formset.is_valid()

    if form_valid and assignment_formset_valid:

        is_new = target_user.pk is None
        user = form.save(commit=False)

        password = None

        if is_new:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*'

            password = ''.join(
                secrets.choice(alphabet)
                for _ in range(12)
            )

            user.set_password(password)

        with transaction.atomic():
            user.save()
            form.save_m2m()

            if user.role == User.Role.FACULTY:

                # Remove assignments belonging to programs no longer assigned
                # to this faculty member.
                assigned_program_ids = list(
                    user.assigned_programs.values_list('pk', flat=True)
                )

                user.class_assignments.exclude(
                    program_id__in=assigned_program_ids
                ).delete()

                assignment_formset.instance = user
                assignment_formset.save()

            else:
                # Non-faculty accounts must not retain teaching assignments.
                user.class_assignments.all().delete()

        if is_new:
            subject = 'Welcome to iSubmit - Your Account Credentials'

            message = (
                f'Hello {user.get_full_name()},\n\n'
                'An account has been created for you on the iSubmit portal.\n\n'
                f'Email: {user.email}\n'
                f'Password: {password}\n\n'
                'Please keep your credentials secure.'
            )

            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False
                )

                messages.success(
                    request,
                    f'Account created for {user.email}. '
                    'Welcome email sent successfully.'
                )

            except Exception:
                messages.warning(
                    request,
                    f'Account created for {user.email}, but the '
                    'welcome email could not be sent. '
                    'Please share the credentials securely.'
                )

        else:
            messages.success(
                request,
                f'Account for {user.email} updated successfully.'
            )

        url = reverse('user_management:user_list')
        return redirect(f'{url}?role={user.role}')

    context = {
        'form': form,
        'assignment_formset': assignment_formset,
        'page_title': 'Edit User' if pk else 'Add User',
        'is_update': bool(pk),
        'object': target_user,
        'show_faculty_fields': show_faculty_fields,
    }

    return render(
        request,
        f'{TEMPLATE_DIR}/user_form.html',
        context
    )


@role_required('ADMIN', 'STAFF')
@require_GET
def assignment_options_view(request):
    """
    Return the available academic years, sections, and courses
    for the selected program.
    """

    program_id = request.GET.get('program')
    academic_year = request.GET.get('academic_year', '')

    if not program_id:
        return JsonResponse({
            'academic_years': [],
            'sections': [],
            'courses': [],
        })

    program = get_object_or_404(Program, pk=program_id)

    academic_years = sorted(
        set(
            program.sections.values_list(
                'academic_year',
                flat=True
            )
        ),
        reverse=True
    )

    sections = []

    if academic_year in academic_years:
        sections = [
            {
                'value': str(section.pk),
                'label': (
                    f'Year {section.year_level} - '
                    f'Section {section.section}'
                ),
            }
            for section in program.sections.filter(
                academic_year=academic_year
            ).order_by('year_level', 'section')
        ]

    courses = [
        {
            'value': str(course.pk),
            'label': f'{course.code} - {course.title}',
        }
        for course in program.courses.order_by('code')
    ]

    return JsonResponse({
        'academic_years': [
            {
                'value': year,
                'label': f'A.Y. {year}',
            }
            for year in academic_years
        ],
        'sections': sections,
        'courses': courses,
    })


@role_required('ADMIN', 'STAFF')
@require_http_methods(['POST'])
def user_toggle_status_view(request, pk):

    if request.user.is_admin:
        manageable_roles = [User.Role.STAFF, User.Role.FACULTY]
    else:
        manageable_roles = [User.Role.FACULTY]

    target_user = get_object_or_404(
        User,
        pk=pk,
        role__in=manageable_roles
    )

    url = reverse('user_management:user_list')
    redirect_url = f'{url}?role={target_user.role}'

    if request.user.pk == target_user.pk:
        messages.error(
            request,
            'You cannot deactivate your own account while signed in.'
        )
        return redirect(redirect_url)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])

    status_label = 'activated' if target_user.is_active else 'deactivated'

    messages.success(
        request,
        f'The account has been {status_label}.'
    )

    return redirect(redirect_url)


@role_required('ADMIN')
@require_http_methods(['POST'])
def user_unlock_view(request, pk):

    target_user = get_object_or_404(
        User,
        pk=pk,
        role__in=[User.Role.STAFF, User.Role.FACULTY]
    )

    url = reverse('user_management:user_list')
    redirect_url = f'{url}?role={target_user.role}'

    if not target_user.is_locked_out:
        messages.info(
            request,
            'This account is not locked out.'
        )
        return redirect(redirect_url)

    axes_reset(username=target_user.email)

    target_user.is_locked_out = False
    target_user.locked_out_until = None

    target_user.save(
        update_fields=['is_locked_out', 'locked_out_until']
    )

    messages.success(
        request,
        'The account lockout has been cleared.'
    )

    return redirect(redirect_url)

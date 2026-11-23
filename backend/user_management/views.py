import secrets
import string

from axes.utils import reset as axes_reset
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_http_methods

from accounts.decorators import access_required
from accounts.models import FacultyProfile
from core.search_utils import all_terms_query
from programs.models import Program
from role_management.models import Role, RoleUserManagementRule
from role_management.services import assign_user_permission_role
from submissions.models import ClassAssignment
from user_management.forms import UserManagementForm, ClassAssignmentFormSet

from user_management.services import (
    can_manage_target_role,
    get_manageable_users,
    get_roles_with_permission
)

User = get_user_model()

TEMPLATE_DIR = 'admin_staff_portal/core/user_mgmt'


def is_faculty_role(role):
    return bool(role and role.is_default and role.code == Role.Code.FACULTY)


def _get_selected_role_from_form(form):
    role_value = form['role'].value()

    if not role_value:
        return None

    try:
        return form.fields['role'].queryset.filter(pk=role_value).first()
    except (TypeError, ValueError):
        return None


@access_required('access_user_management')
@require_http_methods(['GET'])
def user_list_view(request):
    users = (
        get_manageable_users(request.user)
        .select_related('role', 'role__group', 'faculty_profile')
        .prefetch_related('faculty_profile__assigned_programs')
    )

    visible_role_ids = users.order_by().values_list('role_id', flat=True).distinct()

    visible_roles = (
        Role.objects
        .filter(pk__in=visible_role_ids)
        .select_related('group')
        .order_by('group__name')
    )

    selected_role = request.GET.get('role', 'ALL').strip()
    search_query = request.GET.get('q', '').strip()
    faculty_type = request.GET.get('faculty_type', '').strip()
    status = request.GET.get('status', '').strip().lower()
    lockout = request.GET.get('lockout', '').strip().lower()

    if selected_role != 'ALL' and not visible_roles.filter(pk=selected_role).exists():
        selected_role = 'ALL'

    if faculty_type not in FacultyProfile.FacultyType.values:
        faculty_type = ''

    if status not in ('active', 'inactive'):
        status = ''

    if lockout not in ('locked', 'unlocked'):
        lockout = ''

    if selected_role != 'ALL':
        users = users.filter(role_id=selected_role)

    if search_query:
        users = users.filter(
            all_terms_query(search_query, 'first_name', 'middle_name', 'last_name', 'email')
        )

    faculty_role = Role.objects.filter(is_default=True, code=Role.Code.FACULTY).first()
    faculty_role_selected = bool(faculty_role and selected_role == str(faculty_role.pk))

    if faculty_type and (selected_role == 'ALL' or faculty_role_selected):
        users = users.filter(faculty_profile__faculty_type=faculty_type)

    if status == 'active':
        users = users.filter(is_active=True)
    elif status == 'inactive':
        users = users.filter(is_active=False)

    if lockout == 'locked':
        users = users.filter(is_locked_out=True)
    elif lockout == 'unlocked':
        users = users.filter(is_locked_out=False)

    users = users.order_by('last_name', 'first_name', 'pk')
    page_obj = Paginator(users, 7).get_page(request.GET.get('page'))

    if request.user.is_superuser:
        management_rules = {}
    else:
        management_rules = {
            rule.target_role_id: rule
            for rule in RoleUserManagementRule.objects.filter(manager_role_id=request.user.role_id)
        }

    for managed_user in page_obj:
        rule = management_rules.get(managed_user.role_id)

        managed_user.can_edit = request.user.is_superuser or bool(rule and rule.can_edit)
        managed_user.can_change_status = (
            request.user.is_superuser or bool(rule and rule.can_change_status)
        )
        managed_user.can_unlock = request.user.is_superuser or bool(rule and rule.can_unlock)

    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)
    pagination_params['role'] = selected_role

    if selected_role != 'ALL' and not faculty_role_selected:
        pagination_params.pop('faculty_type', None)

    role_choices = [('ALL', 'All Roles')] + [
        (str(role.pk), role.group.name) for role in visible_roles
    ]

    can_add_users = get_roles_with_permission(request.user, action='add').exists()

    context = {
        'users': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'pagination_query': pagination_params.urlencode(),
        'page_title': 'User Management',
        'selected_role': selected_role,
        'current_role': selected_role,
        'role_choices': role_choices,
        'can_add_users': can_add_users,
        'show_faculty_type': selected_role == 'ALL' or faculty_role_selected,
        'faculty_type_choices': FacultyProfile.FacultyType.choices,
        'search_query': search_query,
        'faculty_type_param': faculty_type,
        'status_param': status,
        'lockout_param': lockout,
    }

    return render(request, f'{TEMPLATE_DIR}/user_list.html', context)


@access_required('access_user_management')
@require_http_methods(['GET', 'POST'])
def user_form_view(request, pk=None):
    is_new = pk is None

    assignable_roles = get_roles_with_permission(request.user, action='add')

    if is_new:
        if not assignable_roles.exists():
            raise PermissionDenied('You are not allowed to create accounts for any role.')

        target_user = User()
    else:
        target_user = get_object_or_404(
            get_manageable_users(request.user, action='edit'),
            pk=pk,
        )

    if request.method == 'POST':
        form = UserManagementForm(request.POST, instance=target_user, request_user=request.user)
        form_valid = form.is_valid()
    else:
        initial = {}

        if is_new:
            faculty_role = assignable_roles.filter(is_default=True, code=Role.Code.FACULTY).first()

            if faculty_role:
                initial['role'] = faculty_role

        form = UserManagementForm(instance=target_user, request_user=request.user, initial=initial)
        form_valid = False

    selected_role = _get_selected_role_from_form(form)
    show_faculty_fields = is_faculty_role(selected_role)

    if request.method == 'POST':
        if form_valid and show_faculty_fields:
            allowed_programs = form.cleaned_data.get('assigned_programs', Program.objects.none())
        elif show_faculty_fields:
            selected_program_ids = request.POST.getlist('assigned_programs')
            allowed_programs = form.fields['assigned_programs'].queryset.filter(
                pk__in=selected_program_ids
            )
        else:
            allowed_programs = Program.objects.none()
    elif not is_new and show_faculty_fields:
        faculty_profile = getattr(target_user, 'faculty_profile', None)

        if faculty_profile:
            allowed_programs = faculty_profile.assigned_programs.all()
        else:
            allowed_programs = Program.objects.none()
    else:
        allowed_programs = Program.objects.none()

    if not is_new and show_faculty_fields:
        assignment_queryset = (
            ClassAssignment.objects
            .filter(faculty=target_user, program__in=allowed_programs)
            .select_related('program', 'course')
            .order_by(
                'academic_year', 'semester', 'program__program_name',
                'year_level', 'section', 'course__code',
            )
        )
    else:
        assignment_queryset = ClassAssignment.objects.none()

    assignment_formset = ClassAssignmentFormSet(
        request.POST if (request.method == 'POST' and show_faculty_fields) else None,
        instance=target_user,
        queryset=assignment_queryset,
        prefix='assignments',
        form_kwargs={'allowed_programs': allowed_programs},
    )

    assignment_formset_valid = True

    if request.method == 'POST' and show_faculty_fields:
        assignment_formset_valid = assignment_formset.is_valid()

    if form_valid and assignment_formset_valid:
        user = form.save(commit=False)
        selected_role = form.cleaned_data['role']
        user.role = selected_role

        password = None

        if is_new:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*'
            password = ''.join(secrets.choice(alphabet) for _ in range(12))
            user.set_password(password)

        with transaction.atomic():
            user.save()
            assign_user_permission_role(user, selected_role)

            if is_faculty_role(selected_role):
                faculty_profile, _ = FacultyProfile.objects.get_or_create(user=user)
                faculty_profile.faculty_type = form.cleaned_data['faculty_type']
                faculty_profile.save(update_fields=['faculty_type'])
                faculty_profile.assigned_programs.set(form.cleaned_data['assigned_programs'])

                assigned_program_ids = faculty_profile.assigned_programs.values_list('pk', flat=True)
                user.class_assignments.exclude(program_id__in=assigned_program_ids).delete()

                assignment_formset.instance = user
                assignment_formset.save()
            else:
                FacultyProfile.objects.filter(user=user).delete()
                user.class_assignments.all().delete()

        if is_new:
            subject = 'Your iSubmit Account Has Been Created'
            message = (
                f'Greetings {user.get_full_name()}!\n\n'
                'Your account for the iSubmit portal has been successfully created.\n\n'
                'You may use the following credentials to access your account:\n\n'
                f'Email Address: {user.email}\n'
                f'Temporary Password: {password}\n\n'
                'For your account security, we recommend changing your password '
                'after your first sign-in. Please keep your login credentials '
                'confidential and do not share them with others.\n\n'
                'Should you encounter any difficulties accessing your account, '
                'please contact the system administrator for assistance.\n\n'
                'Thank you.\n\n'
                'Best regards,\n'
                'iSubmit Administration'
            )

            try:
                login_url = request.build_absolute_uri(reverse('accounts:login'))
                html_message = render_to_string('accounts/emails/account_created.html', {
                    'full_name': user.get_full_name(),
                    'email': user.email,
                    'temporary_password': password,
                    'role_name': selected_role.group.name,
                    'login_url': login_url,
                })
                sent_count = send_mail(
                    subject,
                    message + f'\n\nSign in to iSubmit: {login_url}',
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                    html_message=html_message,
                )

                if sent_count == 1:
                    messages.success(
                        request,
                        f'Account created for {user.email}. '
                        'Welcome email sent successfully.',
                    )
                else:
                    messages.warning(
                        request,
                        f'Account created for {user.email}, but the email '
                        'provider did not confirm delivery. Please check '
                        'your email provider configuration.',
                    )
            except Exception:
                messages.warning(
                    request,
                    f'Account created for {user.email}, but the welcome '
                    'email could not be sent. Please check your email '
                    'provider configuration.',
                )
        else:
            messages.success(request, f'Account for {user.email} updated successfully.')

        url = reverse('user_management:user_list')
        return redirect(f'{url}?role={user.role_id}')

    context = {
        'form': form,
        'assignment_formset': assignment_formset,
        'page_title': 'Edit User' if not is_new else 'Add User',
        'is_update': not is_new,
        'object': target_user,
        'show_faculty_fields': show_faculty_fields,
    }

    return render(request, f'{TEMPLATE_DIR}/user_form.html', context)


@access_required('access_user_management')
@require_GET
def assignment_options_view(request):
    faculty_role = Role.objects.filter(is_default=True, code=Role.Code.FACULTY).first()

    if not faculty_role or not (
        can_manage_target_role(request.user, faculty_role, 'add')
        or can_manage_target_role(request.user, faculty_role, 'edit')
    ):
        raise PermissionDenied('You are not allowed to manage Faculty teaching assignments.')

    program_id = request.GET.get('program')
    academic_year = request.GET.get('academic_year', '')

    if not program_id:
        return JsonResponse({'academic_years': [], 'sections': [], 'courses': []})

    program = get_object_or_404(Program, pk=program_id)

    academic_years = sorted(
        set(program.sections.values_list('academic_year', flat=True)),
        reverse=True,
    )

    sections = []

    if academic_year in academic_years:
        sections = [
            {
                'value': str(section.pk),
                'label': f'Year {section.year_level} - Section {section.section}',
            }
            for section in (
                program.sections
                .filter(academic_year=academic_year)
                .order_by('year_level', 'section')
            )
        ]

    courses = [
        {'value': str(course.pk), 'label': f'{course.code} - {course.title}'}
        for course in program.courses.order_by('code')
    ]

    return JsonResponse({
        'academic_years': [{'value': year, 'label': f'A.Y. {year}'} for year in academic_years],
        'sections': sections,
        'courses': courses,
    })


@access_required('access_user_management')
@require_http_methods(['POST'])
def user_toggle_status_view(request, pk):
    target_user = get_object_or_404(
        get_manageable_users(request.user, action='change_status'),
        pk=pk,
    )

    url = reverse('user_management:user_list')
    redirect_url = f'{url}?role={target_user.role_id}'

    if request.user.pk == target_user.pk:
        messages.error(request, 'You cannot deactivate your own account while signed in.')
        return redirect(redirect_url)

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])

    status_label = 'activated' if target_user.is_active else 'deactivated'
    messages.success(request, f'The account has been {status_label}.')

    return redirect(redirect_url)


@access_required('access_user_management')
@require_http_methods(['POST'])
def user_unlock_view(request, pk):
    target_user = get_object_or_404(get_manageable_users(request.user, action='unlock'), pk=pk)

    url = reverse('user_management:user_list')
    redirect_url = f'{url}?role={target_user.role_id}'

    if not target_user.is_locked_out:
        messages.info(request, 'This account is not locked out.')
        return redirect(redirect_url)

    axes_reset(username=target_user.email)

    target_user.is_locked_out = False
    target_user.locked_out_until = None
    target_user.save(update_fields=['is_locked_out', 'locked_out_until'])

    messages.success(request, 'The account lockout has been cleared.')

    return redirect(redirect_url)

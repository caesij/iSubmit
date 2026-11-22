from django.contrib import messages
from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import superuser_required
from notifications.models import (
    NotificationPreference,
    RoleNotificationSetting,
    NOTIFICATION_TYPE_DESCRIPTIONS,
)
from role_management.models import Role, RoleUserManagementRule
from role_management.permissions import ALL_PERMISSION_CODES, ROLE_GROUP_NAMES
from role_management.services import (
    build_permission_pages,
    build_user_management_access_rows,
    ensure_default_roles,
    ensure_default_user_management_rules,
    ensure_role_permissions,
    get_role_content_type,
    get_user_management_target_roles,
    initialize_custom_role_permissions,
    normalize_role_permissions
)


TEMPLATE_DIR = 'admin_staff_portal/core'


def _role_url(request, role):
    return f'{request.path}?role={role.pk}'


def _get_selected_role(role_id):
    if not role_id:
        return None

    return get_object_or_404(Role.objects.select_related('group'), pk=role_id)


def _validate_role_name(name, current_group_id=None):
    name = name.strip()
    if not name:
        return None, 'Enter a name for the role.'

    if len(name) > 150:
        return None, 'Role names cannot exceed 150 characters.'

    existing_groups = Group.objects.filter(name__iexact=name)
    if current_group_id:
        existing_groups = existing_groups.exclude(pk=current_group_id)

    if existing_groups.exists():
        return None, 'A role with that name already exists.'

    return name, None


@superuser_required
@require_http_methods(['GET', 'POST'])
def role_management_view(request):
    ensure_role_permissions()

    default_role_codes = set(Role.objects.filter(is_default=True).values_list('code', flat=True))
    
    if default_role_codes != set(ROLE_GROUP_NAMES):
        ensure_default_roles()

    ensure_default_user_management_rules()

    if request.method == 'POST':
        action = request.POST.get('action')
        role_id = request.POST.get('role_id')

        if action == 'create_role':
            name, error = _validate_role_name(request.POST.get('role_name', ''))
            
            if error:
                messages.error(request, error)
                return redirect(request.path)

            with transaction.atomic():
                group = Group.objects.create(name=name)
                role = Role.objects.create(group=group, is_default=False)
                
                initialize_custom_role_permissions(group)
                ensure_default_user_management_rules()

            messages.success(request, f'The {name} role was created.')
            return redirect(_role_url(request, role))

        selected_role = _get_selected_role(role_id)
        if selected_role is None:
            messages.error(request, 'Please select a role first.')
            return redirect(request.path)

        group = selected_role.group

        if action == 'save_user_management_access':
            if selected_role.is_faculty_role:
                messages.error(request, 'Faculty roles cannot manage other user accounts.')
                
                return redirect(_role_url(request, selected_role))

            target_roles = get_user_management_target_roles(selected_role)

            with transaction.atomic():
                for target_role in target_roles:
                    RoleUserManagementRule.objects.update_or_create(
                        manager_role=selected_role,
                        target_role=target_role,
                        defaults={
                            'can_add': (f'can_add_{target_role.pk}' in request.POST),
                            'can_edit': (f'can_edit_{target_role.pk}' in request.POST),
                            'can_change_status': (f'can_change_status_{target_role.pk}' in request.POST),
                            'can_unlock': (f'can_unlock_{target_role.pk}' in request.POST)
                        }
                    )

            messages.success(request, f'{group.name} user management access updated successfully.')
            
            return redirect(_role_url(request, selected_role))

        if action == 'save_notifications':
            requested_types = set(request.POST.getlist('notification_types'))
            valid_types = {value for value, _ in NotificationPreference.NotificationType.choices}

            if not requested_types.issubset(valid_types):
                messages.error(request, 'Invalid notification categories were submitted.')
                
                return redirect(_role_url(request, selected_role))

            with transaction.atomic():
                for notification_type, _ in NotificationPreference.NotificationType.choices:
                    RoleNotificationSetting.objects.update_or_create(
                        role=selected_role,
                        notification_type=notification_type,
                        defaults={'enabled': notification_type in requested_types}
                    )

            messages.success(request, f'{group.name} notification settings updated successfully.')
            
            return redirect(_role_url(request, selected_role))

        if action == 'rename_role':
            if selected_role.is_default:
                messages.error(request, 'The three default roles cannot be renamed.')
            else:
                name, error = _validate_role_name(
                    request.POST.get('role_name', ''),
                    current_group_id=group.pk,
                )
                if error:
                    messages.error(request, error)
                else:
                    group.name = name
                    group.save(update_fields=['name'])
                    messages.success(request, 'Role name updated successfully.')

            return redirect(_role_url(request, selected_role))

        if action == 'delete_role':
            with transaction.atomic():
                role = get_object_or_404(
                    Role.objects.select_for_update().select_related('group'),
                    pk=role_id,
                )

                if role.is_default:
                    messages.error(request, 'Built-in roles cannot be deleted.')
                else:
                    assigned_user_count = role.users.count()

                    if assigned_user_count:
                        messages.error(
                            request,
                            f'This role cannot be deleted because '
                            f'{assigned_user_count} user(s) are still assigned to it. '
                            'Reassign those users through User Management first.'
                        )
                    else:
                        role_name = role.group.name
                        
                        try:
                            role.group.delete()
                            messages.success(request, f'The {role_name} role was deleted successfully.')
                        except ProtectedError:
                            messages.error(
                                request,
                                'This role cannot be deleted because users are still '
                                'assigned to it. Reassign those users through User '
                                'Management first.'
                            )

            return redirect(request.path)

        if action == 'save_permissions':
            requested_operations = set(request.POST.getlist('operations'))
            selected_codes = normalize_role_permissions(
                selected_role,
                request.POST.getlist('pages'),
                requested_operations
            )

            content_type_id = get_role_content_type().pk
            
            managed_permissions = Permission.objects.filter(
                content_type_id=content_type_id,
                codename__in=ALL_PERMISSION_CODES
            )
            
            selected_permissions = managed_permissions.filter(codename__in=selected_codes)

            permission_through = Group.permissions.through
            with transaction.atomic():
                permission_through.objects.filter(
                    group_id=group.pk,
                    permission_id__in=managed_permissions.values('pk'),
                ).delete()
                group.permissions.add(*selected_permissions)

            messages.success(request, f'{group.name} permissions updated successfully.')
            
            return redirect(_role_url(request, selected_role))

        messages.error(request, 'The requested role management action is not valid.')
        return redirect(_role_url(request, selected_role))

    selected_role = _get_selected_role(request.GET.get('role'))
    role_type = request.GET.get('role_type', 'all')

    if role_type not in ('all', 'default', 'custom'):
        role_type = 'all'

    search_query = request.GET.get('q', '').strip()
    role_records = Role.objects.select_related('group')

    if role_type == 'default':
        role_records = role_records.filter(is_default=True)
    elif role_type == 'custom':
        role_records = role_records.filter(is_default=False)

    if search_query:
        role_records = role_records.filter(group__name__icontains=search_query)

    roles = [
        {
            'id': role.pk,
            'label': role.group.name,
            'selected': (
                selected_role is not None and role.pk == selected_role.pk
            ),
            'is_default': role.is_default,
        }
        for role in role_records
    ]

    permission_pages = []
    assigned_user_count = 0
    user_management_access_rows = []

    if selected_role:
        group = selected_role.group
        content_type_id = get_role_content_type().pk

        selected_codes = set(
            group.permissions.filter(
                content_type_id=content_type_id,
                codename__in=ALL_PERMISSION_CODES
            ).values_list('codename', flat=True)
        )

        permission_pages = build_permission_pages(selected_role, selected_codes)
        
        assigned_user_count = selected_role.users.count()

        if not selected_role.is_faculty_role:
            user_management_access_rows = (build_user_management_access_rows(selected_role))

    enabled_notification_types = set()
    if selected_role:
        enabled_notification_types = set(
            RoleNotificationSetting.objects.filter(
                role=selected_role,
                enabled=True,
            ).values_list('notification_type', flat=True)
        )

    role_notification_types = [
        {
            'value': value,
            'label': label,
            'description': NOTIFICATION_TYPE_DESCRIPTIONS.get(value, ''),
            'checked': value in enabled_notification_types,
        }
        for value, label in NotificationPreference.NotificationType.choices
    ]

    context = {
        'roles': roles,
        'role_type': role_type,
        'search_query': search_query,
        'selected_role': selected_role,
        'selected_role_name': (selected_role.group.name if selected_role else None),
        'permission_pages': permission_pages,
        'role_notification_types': role_notification_types,
        'assigned_user_count': assigned_user_count,
        'user_management_access_rows': user_management_access_rows
    }

    return render(request, f'{TEMPLATE_DIR}/role_management.html', context)

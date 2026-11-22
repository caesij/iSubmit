from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from role_management.models import Role, RoleUserManagementRule
from role_management.permissions import (
    ADMIN_SIDE_ROLE_CODES,
    ALL_PERMISSION_CODES,
    COMMON_DEFAULT_PERMISSION_CODES,
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSION_DETAILS,
    PERMISSION_PAGES,
    ROLE_GROUP_NAMES
)


User = get_user_model()


def get_role_content_type():
    return ContentType.objects.get_for_model(get_user_model())


def ensure_role_permissions():
    content_type = get_role_content_type()

    Permission.objects.bulk_create(
        [
            Permission(
                content_type=content_type,
                codename=codename,
                name=PERMISSION_DETAILS[codename][0],
            )
            for codename in ALL_PERMISSION_CODES
        ],
        ignore_conflicts=True,
    )

    return Permission.objects.filter(content_type=content_type, codename__in=ALL_PERMISSION_CODES)


def get_role_key(role):
    if not role or not role.is_default:
        return None

    return role.code if role.code in ROLE_GROUP_NAMES else None


def get_permission_pages_for_role(role):
    if not role:
        return ()

    if not role.is_default:
        return tuple(
            page
            for page in PERMISSION_PAGES
            if page['available_to'] & ADMIN_SIDE_ROLE_CODES
        )

    role_key = get_role_key(role)

    if not role_key:
        return ()

    return tuple(
        page
        for page in PERMISSION_PAGES
        if role_key in page['available_to']
    )


def build_permission_pages(role, selected_codes):
    selected_codes = set(selected_codes)
    permission_pages = []

    for page in get_permission_pages_for_role(role):
        page_code = page['access_codename']
        page_checked = page_code in selected_codes

        operations = []
        for operation in page['operations']:
            operations.append({
                **operation,
                'checked': (page_checked and operation['codename'] in selected_codes),
            })

        permission_pages.append({
            'key': page['key'],
            'title': page['title'],
            'description': page['description'],
            'access_codename': page_code,
            'checked': page_checked,
            'operations': operations
        })

    return permission_pages


def normalize_role_permissions(role, selected_page_codes, selected_operation_codes):
    pages = get_permission_pages_for_role(role)
    available_page_codes = {page['access_codename'] for page in pages}
    
    selected_pages = set(selected_page_codes) & available_page_codes

    operation_definitions = {}
    for page in pages:
        page_code = page['access_codename']
        for operation in page['operations']:
            operation_definitions[operation['codename']] = {
                'page_code': page_code,
                'requires': set(operation.get('requires', ())),
            }

    selected_operations = {
        code
        for code in set(selected_operation_codes)
        if (
            code in operation_definitions
            and operation_definitions[code]['page_code'] in selected_pages
        )
    }

    changed = True
    while changed:
        changed = False
        for code in tuple(selected_operations):
            required_operations = operation_definitions[code]['requires']
            if not required_operations.issubset(selected_operations):
                selected_operations.remove(code)
                changed = True

    return selected_pages | selected_operations


def initialize_custom_role_permissions(group):
    permissions = ensure_role_permissions()
    default_permissions = permissions.filter(codename__in=COMMON_DEFAULT_PERMISSION_CODES)
    group.permissions.set(default_permissions)


def get_user_management_target_roles(manager_role):
    roles = Role.objects.select_related('group')

    if not manager_role or manager_role.is_faculty_role:
        return roles.none()

    return roles.order_by('group__name')


def build_user_management_access_rows(manager_role):
    target_roles = get_user_management_target_roles(manager_role)
    rules = {
        rule.target_role_id: rule
        for rule in RoleUserManagementRule.objects.filter(manager_role=manager_role)
    }

    rows = []
    for target_role in target_roles:
        rule = rules.get(target_role.pk)
        rows.append({
            'target_role': target_role,
            'can_add': bool(rule and rule.can_add),
            'can_edit': bool(rule and rule.can_edit),
            'can_change_status': bool(rule and rule.can_change_status),
            'can_unlock': bool(rule and rule.can_unlock)
        })

    return rows


def ensure_default_user_management_rules():
    admin_role = Role.objects.filter(is_default=True, code=Role.Code.ADMIN).first()
    staff_role = Role.objects.filter(is_default=True, code=Role.Code.STAFF).first()
    faculty_role = Role.objects.filter(is_default=True, code=Role.Code.FACULTY).first()

    if admin_role:
        for target_role in Role.objects.all():
            RoleUserManagementRule.objects.get_or_create(
                manager_role=admin_role,
                target_role=target_role,
                defaults={
                    'can_add': True,
                    'can_edit': True,
                    'can_change_status': True,
                    'can_unlock': True
                },
            )

    if staff_role and faculty_role:
        RoleUserManagementRule.objects.get_or_create(
            manager_role=staff_role,
            target_role=faculty_role,
            defaults={
                'can_add': True,
                'can_edit': True,
                'can_change_status': True,
                'can_unlock': False
            },
        )


def ensure_default_roles():
    permissions = ensure_role_permissions()
    groups = {}

    for role_code, group_name in ROLE_GROUP_NAMES.items():
        group, group_created = Group.objects.get_or_create(name=group_name)

        role, _ = Role.objects.get_or_create(
            group=group,
            defaults={'code': role_code, 'is_default': True}
        )

        update_fields = []

        if role.code != role_code:
            conflicting_role = (
                Role.objects.filter(code=role_code)
                .exclude(pk=role.pk)
                .first()
            )
            if conflicting_role:
                raise ValueError(
                    f'The role code {role_code} is already assigned to another role: {conflicting_role.group.name}.'
                )

            role.code = role_code
            update_fields.append('code')

        if not role.is_default:
            role.is_default = True
            update_fields.append('is_default')

        if update_fields:
            role.save(update_fields=update_fields)

        groups[role_code] = group

        if group_created:
            group.permissions.set(permissions.filter(codename__in=DEFAULT_ROLE_PERMISSIONS[role_code]))

    ensure_default_user_management_rules()
    return groups


def assign_user_permission_role(user, permission_role):
    if user.is_superuser:
        return

    managed_group_ids = list(Role.objects.values_list('group_id', flat=True))

    if managed_group_ids:
        user.groups.remove(*managed_group_ids)

    user.groups.add(permission_role.group)

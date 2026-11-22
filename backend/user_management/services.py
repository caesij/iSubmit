from django.contrib.auth import get_user_model
from django.db.models import Q

from role_management.models import Role, RoleUserManagementRule


User = get_user_model()

ACTION_FIELDS = {
    'add': 'can_add',
    'edit': 'can_edit',
    'change_status': 'can_change_status',
    'unlock': 'can_unlock'
}


def get_roles_with_permission(user, action=None):
    roles = Role.objects.select_related('group')

    if user is None:
        return roles.none()

    if user.is_superuser:
        return roles.order_by('group__name')

    if not user.role_id or user.role.is_faculty_role:
        return roles.none()

    rules = RoleUserManagementRule.objects.filter(manager_role_id=user.role_id)

    if action is not None:
        field = ACTION_FIELDS.get(action)
        if field is None:
            return roles.none()
        rules = rules.filter(**{field: True})
    else:
        rules = rules.filter(
            Q(can_edit=True)
            | Q(can_change_status=True)
            | Q(can_unlock=True)
        )

    roles = roles.filter(pk__in=rules.values('target_role_id'))

    return roles.order_by('group__name')


def get_manageable_users(user, action=None):
    users = User.objects.filter(is_superuser=False)
    manageable_roles = get_roles_with_permission(user, action=action)
    return users.filter(role_id__in=manageable_roles.values('pk'))


def can_manage_target_role(user, target_role, action):
    if user is None or target_role is None:
        return False

    if user.is_superuser:
        return True

    if not user.role_id or user.role.is_faculty_role:
        return False

    field = ACTION_FIELDS.get(action)
    
    if field is None:
        return False

    return RoleUserManagementRule.objects.filter(
        manager_role_id=user.role_id,
        target_role=target_role,
        **{field: True}
    ).exists()

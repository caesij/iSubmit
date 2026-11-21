from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db.models.signals import m2m_changed, post_migrate, post_save
from django.dispatch import receiver

from role_management.permissions import ROLE_GROUP_NAMES
from role_management.services import ensure_default_roles

User = get_user_model()


@receiver(post_migrate, sender=apps.get_app_config('role_management'))
def create_default_role_groups(sender, **kwargs):
    ensure_default_roles()


@receiver(post_save, sender=User)
def ensure_superuser_admin_group(sender, instance, raw=False, **kwargs):
    if raw or not instance.is_superuser:
        return

    admin_group = Group.objects.filter(name=ROLE_GROUP_NAMES['ADMIN']).first()

    if admin_group:
        instance.groups.add(admin_group)


@receiver(m2m_changed, sender=User.groups.through)
def keep_superuser_in_admin_group(
    sender,
    instance,
    action,
    reverse,
    pk_set=None,
    **kwargs
):
    admin_group_name = ROLE_GROUP_NAMES['ADMIN']

    if reverse:
        if instance.name != admin_group_name:
            return

        if action == 'pre_remove' and pk_set and User.objects.filter(
            pk__in=pk_set,
            is_superuser=True,
        ).exists():
            raise ValidationError('The system superuser must remain in the Admin role.')

        if action == 'pre_clear' and instance.user_set.filter(
            is_superuser=True
        ).exists():
            raise ValidationError('The system superuser must remain in the Admin role.')

        return

    if not instance.is_superuser or action not in ('post_remove', 'post_clear'):
        return

    admin_group = Group.objects.filter(name=admin_group_name).only('pk').first()

    if admin_group and not instance.groups.filter(pk=admin_group.pk).exists():
        instance.groups.add(admin_group)


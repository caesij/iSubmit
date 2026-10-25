from django.conf import settings
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from django.utils import timezone

from axes.signals import user_locked_out

from notifications.models import NotificationPreference
from notifications.services import notify_roles


User = get_user_model()


@receiver(user_locked_out, dispatch_uid='accounts.handle_user_lockout')
def handle_user_lockout(
    sender,
    request,
    username=None,
    ip_address=None,
    **kwargs,
):
    if not username:
        return

    locked_user = User.objects.filter(
        email__iexact=username,
    ).first()

    if locked_user is None:
        return

    newly_locked = User.objects.filter(
        pk=locked_user.pk,
        is_locked_out=False
    ).update(
        is_locked_out=True,
        locked_out_until=(timezone.now() + settings.AXES_COOLOFF_TIME)
    )

    if not newly_locked:
        return

    if locked_user.is_admin or locked_user.is_superuser:
        return

    notify_roles(
        roles=[User.Role.ADMIN],
        notification_type=(NotificationPreference.NotificationType.SECURITY_NOTIFICATIONS),
        title='Account Locked Out',
        message=(
            f'{locked_user.get_full_name() or locked_user.email} '
            'was locked out after repeated failed sign-in attempts.'
        ),
    )
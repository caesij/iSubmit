from django.core.mail import send_mail
from django.conf import settings

from accounts.models import (
    Notification,
    NotificationPreference,
)


def notify(
    user,
    notification_type,
    title,
    message,
    link='',
):
    try:
        pref = NotificationPreference.objects.get(
            user=user,
            notification_type=notification_type,
        )
    except NotificationPreference.DoesNotExist:
        pref = None

    if pref and not pref.enabled:
        return

    system_on = pref.system_enabled if pref else True
    email_on = pref.email_enabled if pref else True

    if system_on:
        Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )

    if email_on:
        try:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
        except Exception:
            pass
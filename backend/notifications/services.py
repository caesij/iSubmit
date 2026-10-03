from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth import get_user_model

from notifications.models import Notification, NotificationPreference
from core.realtime import send_to_user

User = get_user_model()


def create_notif(user, notification_type, title, message, link=''):
    allowed_types = NotificationPreference.ROLE_TYPES.get(user.role, [])

    if notification_type not in allowed_types:
        return None

    preference, _ = NotificationPreference.objects.get_or_create(
        user=user,
        notification_type=notification_type,
        defaults={
            'enabled': True,
            'system_enabled': True,
            'email_enabled': True,
        },
    )

    if not preference.enabled:
        return None

    notification = None

    if preference.system_enabled:
        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )

        send_to_user(
            user,
            'notification.new',
            {
                'id': notification.id,
                'notification_type': notification.notification_type,
                'title': notification.title,
                'message': notification.message,
                'link': notification.link,
                'created_at': timezone.localtime(
                    notification.created_at
                ).isoformat(),
            },
        )

    if preference.email_enabled:
        send_mail(
            subject=title,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )

    return notification


def notify_roles(roles, notification_type, title, message, link=''):
    users = User.objects.filter(role__in=roles, is_active=True)

    notifications = []

    for user in users:
        notification = create_notif(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link,
        )

        if notification:
            notifications.append(notification)

    return notifications
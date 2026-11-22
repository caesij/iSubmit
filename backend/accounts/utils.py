from notifications.models import NotificationPreference
from notifications.services import get_allowed_notification_types


def get_or_create_preferences(user):
    allowed_types = get_allowed_notification_types(user)
    if not allowed_types:
        return []

    NotificationPreference.objects.bulk_create(
        [
            NotificationPreference(
                user=user,
                notification_type=notification_type,
            )
            for notification_type in allowed_types
        ],
        ignore_conflicts=True
    )

    return list(
        NotificationPreference.objects.filter(
            user=user,
            notification_type__in=allowed_types,
        ).order_by('notification_type')
    )

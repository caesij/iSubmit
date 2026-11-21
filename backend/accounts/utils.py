from notifications.models import NotificationPreference
from notifications.services import get_allowed_notification_types


def validate_portal_access(user, login_type):
    if login_type == 'FACULTY':
        if not user.is_faculty:
            return False, 'Only Faculty accounts can sign in through this tab.'

    elif login_type == 'ADMIN':
        if user.is_faculty:
            return False, 'Faculty members must sign in through the Faculty tab.'

        if not (user.is_admin or user.is_staff_role):
            return False, 'This sign-in option is only available to Admin and Staff accounts.'

    return True, None


def get_or_create_preferences(user):
    """Return preferences for events enabled on the user's assigned role."""
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
        ignore_conflicts=True,
    )

    return list(
        NotificationPreference.objects.filter(
            user=user,
            notification_type__in=allowed_types,
        ).order_by('notification_type')
    )

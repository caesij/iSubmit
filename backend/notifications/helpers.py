from notifications.models import Notification, NotificationPreference
from notifications.services import get_allowed_notification_types


def get_role_based_notifications(request):
    user = request.user
    notifications = Notification.objects.filter(user=user)

    # Show event filters the user's role can currently receive, plus events
    # already present in their history so role-setting changes do not hide old records.
    available_types = set(get_allowed_notification_types(user))
    available_types.update(
        Notification.objects.filter(user=user)
        .values_list('notification_type', flat=True)
        .distinct()
    )

    selected_type = request.GET.get('type', '')
    read_status = request.GET.get('read', '')
    sort_by = request.GET.get('sort', 'newest')

    if selected_type:
        if selected_type in available_types:
            notifications = notifications.filter(notification_type=selected_type)
        else:
            notifications = notifications.none()

    if read_status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_status == 'read':
        notifications = notifications.filter(is_read=True)

    notifications = notifications.order_by(
        'created_at' if sort_by == 'oldest' else '-created_at'
    )

    notification_type_choices = [
        choice
        for choice in NotificationPreference.NotificationType.choices
        if choice[0] in available_types
    ]

    return {
        'notifications': notifications,
        'notification_type_choices': notification_type_choices,
        'selected_type': selected_type if selected_type in available_types else '',
        'selected_read': read_status,
        'selected_sort': sort_by,
    }

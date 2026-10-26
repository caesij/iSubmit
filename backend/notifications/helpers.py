from notifications.models import Notification, NotificationPreference

def get_role_based_notifications(request):
    user = request.user

    allowed_types = NotificationPreference.ROLE_TYPES.get(user.role, [])

    notifications = Notification.objects.filter( user=user, notification_type__in=allowed_types)

    notification_type = request.GET.get('type', '')
    read_status = request.GET.get('read', '')
    sort_by = request.GET.get('sort', 'newest')

    if notification_type:
        if notification_type in allowed_types:
            notifications = notifications.filter(notification_type=notification_type)
        else:
            notifications = notifications.none()

    if read_status == 'unread':
        notifications = notifications.filter(is_read=False)
    elif read_status == 'read':
        notifications = notifications.filter(is_read=True)

    if sort_by == 'oldest':
        notifications = notifications.order_by('created_at')
    else:
        notifications = notifications.order_by('-created_at')

    notification_type_choices = [
        (value, label)
        for value, label in NotificationPreference.NotificationType.choices
        if value in allowed_types
    ]

    return {
        'notifications': notifications,
        'notification_type_choices': notification_type_choices,
        'selected_type': (notification_type if notification_type in allowed_types else ''),
        'selected_read': read_status,
        'selected_sort': sort_by
    }

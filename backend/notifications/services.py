from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.auth import get_user_model

from notifications.models import Notification, NotificationPreference
from core.realtime import send_to_user
from core.date_formatting import format_display_date, format_display_time

User = get_user_model()


def create_notif(
    user,
    notification_type,
    title,
    message,
    link='',
    email_subject=None,
    email_message=None
):
    allowed_types = NotificationPreference.ROLE_TYPES.get(user.role, [])

    if notification_type not in allowed_types:
        return None

    preference, _ = NotificationPreference.objects.get_or_create(
        user=user,
        notification_type=notification_type,
        defaults={
            'enabled': True,
            'system_enabled': True,
            'email_enabled': True
        }
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
            link=link
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
                ).isoformat()
            }
        )

    if preference.email_enabled:
        send_mail(
            subject=email_subject or title,
            message=email_message or message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )

    return notification


def build_approval_email(
    recipient,
    document_names,
    approved_by,
    approved_at
):
    names = list(document_names)
    document_label = (
        names[0]
        if len(names) == 1
        else f'{len(names)} submitted documents'
    )
    approver_name = approved_by.get_full_name() or approved_by.email
    approved_date = format_display_date(approved_at, recipient)
    approved_time = format_display_time(approved_at, recipient)
    document_lines = '\n'.join(f'- {name}' for name in names)

    subject = f'Document approved: {document_label}'
    message = (
        f'Hello {recipient.get_full_name() or recipient.email},\n\n'
        f'{document_label} has been approved.\n\n'
        f'Document(s):\n{document_lines}\n\n'
        f'Status: Approved\n'
        f'Approved by: {approver_name}\n'
        f'Approved on: {approved_date} at {approved_time}\n\n'
        'Your approved document is now available in My Documents.\n\n'
        'Thank you,\n'
        'iSubmit'
    )
    return subject, message


def notify_roles(roles, notification_type, title, message, link=''):
    users = User.objects.filter(role__in=roles, is_active=True)

    notifications = []

    for user in users:
        notification = create_notif(
            user=user,
            notification_type=notification_type,
            title=title,
            message=message,
            link=link
        )

        if notification:
            notifications.append(notification)

    return notifications
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mass_mail
from django.db import transaction
from django.utils import timezone

from core.date_formatting import format_display_date, format_display_time
from core.realtime import send_to_user
from notifications.models import (
    Notification,
    NotificationPreference,
    NOTIFICATION_TYPE_AUDIENCES,
    RoleNotificationSetting,
)

logger = logging.getLogger(__name__)
User = get_user_model()

NotificationType = NotificationPreference.NotificationType


DEFAULT_ROLE_NOTIFICATION_TYPES = {
    'ADMIN': {
        NotificationType.NEW_DOCUMENT_SUBMITTED,
        NotificationType.DOCUMENT_RESUBMITTED,
        NotificationType.ALL_REQUIREMENTS_COMPLETED,
        NotificationType.ACCOUNT_LOCKED_OUT,
        NotificationType.NEW_LOGIN,
        NotificationType.SYSTEM_ANNOUNCEMENT,
    },
    'STAFF': {
        NotificationType.NEW_DOCUMENT_SUBMITTED,
        NotificationType.DOCUMENT_RESUBMITTED,
        NotificationType.ALL_REQUIREMENTS_COMPLETED,
        NotificationType.ACCOUNT_LOCKED_OUT,
        NotificationType.NEW_LOGIN,
        NotificationType.SYSTEM_ANNOUNCEMENT,
    },
    'FACULTY': {
        NotificationType.SUBMISSION_UNDER_REVIEW,
        NotificationType.SUBMISSION_REVIEWED,
        NotificationType.SUBMISSION_NEEDS_REVISION,
        NotificationType.SUBMISSION_APPROVED,
        NotificationType.REQUIREMENTS_OPENED,
        NotificationType.DEADLINE_CHANGED,
        NotificationType.NEW_LOGIN,
        NotificationType.SYSTEM_ANNOUNCEMENT,
    },
}


def get_notification_types_for_role(role):
    """Return only the event switches relevant to this role's audience."""
    audience = 'FACULTY' if role and role.is_faculty_role else 'ADMIN'
    allowed_audiences = {audience, 'ALL'}

    return [
        (value, label)
        for value, label in NotificationType.choices
        if NOTIFICATION_TYPE_AUDIENCES[value] in allowed_audiences
    ]


def get_allowed_notification_types(user):
    if not user or not user.is_authenticated or not user.role_id:
        return []

    return list(
        RoleNotificationSetting.objects.filter(
            role_id=user.role_id,
            enabled=True,
        ).values_list('notification_type', flat=True)
    )


def ensure_default_role_notification_settings():
    from role_management.models import Role

    roles = Role.objects.filter(
        is_default=True,
        code__in=DEFAULT_ROLE_NOTIFICATION_TYPES,
    ).only('id', 'code')

    settings_to_create = [
        RoleNotificationSetting(
            role=role,
            notification_type=notification_type,
            enabled=notification_type in DEFAULT_ROLE_NOTIFICATION_TYPES[role.code],
        )
        for role in roles
        for notification_type, _ in NotificationType.choices
    ]

    RoleNotificationSetting.objects.bulk_create(
        settings_to_create,
        ignore_conflicts=True,
    )


def _value_for_user(value, user):
    return value(user) if callable(value) else value


def _send_realtime_notifications(recipients, notifications):
    for user, notification in zip(recipients, notifications):
        try:
            send_to_user(
                user,
                'notification.new',
                {
                    'id': notification.pk,
                    'notification_type': notification.notification_type,
                    'title': notification.title,
                    'message': notification.message,
                    'link': notification.link,
                    'created_at': timezone.localtime(
                        notification.created_at
                    ).isoformat(),
                },
            )
        except Exception:
            logger.exception(
                'Could not broadcast notification %s to user %s.',
                notification.pk,
                user.pk,
            )


def notify_users(
    users,
    notification_type,
    title,
    message,
    link='',
    email_subject=None,
    email_message=None,
    send_email_notification=True,
    *,
    role_settings_checked=False,
):
    """Notify an explicit user queryset/list, applying role and user settings."""
    if hasattr(users, 'filter'):
        recipients = list(users.filter(is_active=True).distinct())
    else:
        unique_users = {
            user.pk: user
            for user in users
            if user and user.is_active and user.pk
        }
        recipients = list(unique_users.values())

    if not recipients:
        return 0

    if not role_settings_checked:
        role_ids = {user.role_id for user in recipients if user.role_id}
        enabled_role_ids = set(
            RoleNotificationSetting.objects.filter(
                role_id__in=role_ids,
                notification_type=notification_type,
                enabled=True,
            ).values_list('role_id', flat=True)
        )
        recipients = [
            user for user in recipients
            if user.role_id in enabled_role_ids
        ]

    if not recipients:
        return 0

    user_ids = [user.pk for user in recipients]
    preferences = list(
        NotificationPreference.objects.filter(
            user_id__in=user_ids,
            notification_type=notification_type,
        )
    )
    preferences_by_user = {preference.user_id: preference for preference in preferences}

    missing_preferences = [
        NotificationPreference(
            user_id=user.pk,
            notification_type=notification_type,
        )
        for user in recipients
        if user.pk not in preferences_by_user
    ]

    if missing_preferences:
        NotificationPreference.objects.bulk_create(
            missing_preferences,
            ignore_conflicts=True,
        )
        preferences_by_user = {
            preference.user_id: preference
            for preference in NotificationPreference.objects.filter(
                user_id__in=user_ids,
                notification_type=notification_type,
            )
        }

    deliveries = [
        (user, preferences_by_user[user.pk])
        for user in recipients
        if (
            user.pk in preferences_by_user
            and preferences_by_user[user.pk].enabled
            and (
                preferences_by_user[user.pk].system_enabled
                or (
                    send_email_notification
                    and preferences_by_user[user.pk].email_enabled
                )
            )
        )
    ]

    if not deliveries:
        return 0

    notification_recipients = []
    notification_records = []
    email_messages = []

    for user, preference in deliveries:
        user_message = _value_for_user(message, user)

        if preference.system_enabled:
            notification_recipients.append(user)
            notification_records.append(
                Notification(
                    user=user,
                    notification_type=notification_type,
                    title=_value_for_user(title, user),
                    message=user_message,
                    link=_value_for_user(link, user) or '',
                )
            )

        if send_email_notification and preference.email_enabled:
            email_messages.append((
                _value_for_user(email_subject, user) or _value_for_user(title, user),
                _value_for_user(email_message, user) if email_message is not None else user_message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
            ))

    created_notifications = Notification.objects.bulk_create(notification_records)

    if created_notifications:
        transaction.on_commit(
            lambda: _send_realtime_notifications(
                notification_recipients,
                created_notifications,
            )
        )

    if email_messages:
        transaction.on_commit(
            lambda: send_mass_mail(email_messages, fail_silently=True)
        )

    return len(deliveries)


def notify_user(
    user,
    notification_type,
    title,
    message,
    link='',
    email_subject=None,
    email_message=None,
    send_email_notification=True,
):
    return notify_users(
        [user],
        notification_type,
        title,
        message,
        link=link,
        email_subject=email_subject,
        email_message=email_message,
        send_email_notification=send_email_notification,
    )


def notify_role_subscribers(
    notification_type,
    title,
    message,
    link='',
    email_subject=None,
    email_message=None,
    send_email_notification=True,
):
    """Notify active users whose roles have enabled this specific event."""
    enabled_role_ids = RoleNotificationSetting.objects.filter(
        notification_type=notification_type,
        enabled=True,
    ).values('role_id')

    users = User.objects.filter(
        is_active=True,
        role_id__in=enabled_role_ids,
    )

    return notify_users(
        users,
        notification_type,
        title,
        message,
        link=link,
        email_subject=email_subject,
        email_message=email_message,
        send_email_notification=send_email_notification,
        role_settings_checked=True,
    )


def build_approval_email(
    recipient,
    document_names,
    approved_by,
    approved_at,
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

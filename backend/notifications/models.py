from django.db import models
from django.conf import settings

class NotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    class NotificationType(models.TextChoices):
        SYSTEM_NOTIFICATIONS = 'SYSTEM_NOTIFICATIONS', 'System Notifications'
        SUBMISSION_NOTIFICATIONS = 'SUBMISSION_NOTIFICATIONS', 'Submission Notifications'
        SECURITY_NOTIFICATIONS = 'SECURITY_NOTIFICATIONS', 'Security Notifications'

    DESCRIPTIONS = {
        'FACULTY': {
            NotificationType.SYSTEM_NOTIFICATIONS:
                'Receive notifications about requirement assignments, announcements, and scheduled maintenance.',
            NotificationType.SUBMISSION_NOTIFICATIONS:
                'Receive notifications about document submissions, review results, and submission deadlines.',
            NotificationType.SECURITY_NOTIFICATIONS:
                'Receive notifications about account logins and other security-related activities.',
        },
        'ADMIN': {
            NotificationType.SUBMISSION_NOTIFICATIONS:
                'Receive notifications when faculty members submit or resubmit required documents.',
            NotificationType.SECURITY_NOTIFICATIONS:
                'Receive notifications about account logins and other security-related activities.',
        },
        'STAFF': {
            NotificationType.SUBMISSION_NOTIFICATIONS:
                'Receive notifications when faculty members submit or resubmit required documents.',
            NotificationType.SECURITY_NOTIFICATIONS:
                'Receive notifications about account logins and other security-related activities.',
        }
    }

    ROLE_TYPES = {
        'FACULTY': [
            NotificationType.SYSTEM_NOTIFICATIONS,
            NotificationType.SUBMISSION_NOTIFICATIONS,
            NotificationType.SECURITY_NOTIFICATIONS
        ],
        'ADMIN': [
            NotificationType.SUBMISSION_NOTIFICATIONS,
            NotificationType.SECURITY_NOTIFICATIONS
        ],
        'STAFF': [
            NotificationType.SUBMISSION_NOTIFICATIONS,
            NotificationType.SECURITY_NOTIFICATIONS
        ],
    }
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices
    )

    enabled = models.BooleanField(default=True)
    email_enabled = models.BooleanField(default=True)
    system_enabled = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'notification_type'],
                name='unique_user_notification_type'
            )
        ]

    @property
    def description(self):
        role = self.user.role
        role_descriptions = self.DESCRIPTIONS.get(role, {})
        return role_descriptions.get(self.notification_type, '')

    def __str__(self):
        return f'{self.user.email} - {self.get_notification_type_display()}'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationPreference.NotificationType.choices,
    )
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['user', 'is_read', '-created_at'],
                name='notif_user_read_date_idx'
            ),
            models.Index(
                fields=['user', '-created_at'],
                name='notif_user_date_idx'
            ),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.title}'
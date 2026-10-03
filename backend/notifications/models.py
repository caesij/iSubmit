from django.db import models
from django.conf import settings


class NotificationPreference(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    
    class NotificationType(models.TextChoices):
        SYSTEM_ANNOUNCEMENT = 'SYSTEM_ANNOUNCEMENT', 'System Announcement'
        DOCUMENT_UPDATES = 'DOCUMENT_UPDATES', 'Document Updates'
        SUBMISSION_UPDATES = 'SUBMISSION_UPDATES', 'Submission Updates'
        SUBMISSION_REMINDERS = 'SUBMISSION_REMINDERS', 'Submission Reminders'
        APPROVAL_REJECTIONS = 'APPROVAL_REJECTIONS', 'Approval and Rejections'
        SECURITY_ALERTS = 'SECURITY_ALERTS', 'Security Alerts'

    DESCRIPTIONS = {
        NotificationType.SYSTEM_ANNOUNCEMENT: 'Receive alerts about important system announcement and updates.',
        NotificationType.DOCUMENT_UPDATES: 'Updates about your submitted documents.',
        NotificationType.SUBMISSION_UPDATES: 'Get notified on submissions status.',
        NotificationType.SUBMISSION_REMINDERS: 'Reminders for pending submission and deadlines.',
        NotificationType.APPROVAL_REJECTIONS: 'Notifications about documents approvals or rejections.',
        NotificationType.SECURITY_ALERTS: 'Login alerts and security-related notifications.',
    }

    ROLE_TYPES = {
        'FACULTY': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.DOCUMENT_UPDATES,
            NotificationType.SUBMISSION_REMINDERS,
            NotificationType.APPROVAL_REJECTIONS,
            NotificationType.SECURITY_ALERTS,
        ],
        'ADMIN': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.SUBMISSION_UPDATES,
            NotificationType.SECURITY_ALERTS,
        ],
        'STAFF': [
            NotificationType.SYSTEM_ANNOUNCEMENT,
            NotificationType.SUBMISSION_UPDATES,
            NotificationType.SECURITY_ALERTS,
        ],
    }
    
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
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
        return self.DESCRIPTIONS.get(self.notification_type, '')

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
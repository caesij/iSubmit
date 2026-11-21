from django.conf import settings
from django.db import models


class NotificationPreference(models.Model):
    class NotificationType(models.TextChoices):
        NEW_DOCUMENT_SUBMITTED = 'NEW_DOCUMENT_SUBMITTED', 'New Document Submitted'
        DOCUMENT_RESUBMITTED = 'DOCUMENT_RESUBMITTED', 'Document Resubmitted'
        ALL_REQUIREMENTS_COMPLETED = 'ALL_REQUIREMENTS_COMPLETED', 'All Required Documents Submitted'

        SUBMISSION_UNDER_REVIEW = 'SUBMISSION_UNDER_REVIEW', 'Submission Under Review'
        SUBMISSION_REVIEWED = 'SUBMISSION_REVIEWED', 'Submission Reviewed'
        SUBMISSION_NEEDS_REVISION = 'SUBMISSION_NEEDS_REVISION', 'Submission Needs Revision'
        SUBMISSION_APPROVED = 'SUBMISSION_APPROVED', 'Submission Approved'

        REQUIREMENTS_OPENED = 'REQUIREMENTS_OPENED', 'New Submission Requirements'
        DEADLINE_CHANGED = 'DEADLINE_CHANGED', 'Submission Deadline Changed'

        ACCOUNT_LOCKED_OUT = 'ACCOUNT_LOCKED_OUT', 'Account Locked Out'
        NEW_LOGIN = 'NEW_LOGIN', 'New Login Detected'
        SYSTEM_ANNOUNCEMENT = 'SYSTEM_ANNOUNCEMENT', 'System Announcement'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences',
    )
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
                name='unique_user_notification_type',
            ),
        ]
        ordering = ('notification_type',)

    @property
    def description(self):
        return NOTIFICATION_TYPE_DESCRIPTIONS.get(self.notification_type, '')

    def __str__(self):
        return f'{self.user.email} - {self.get_notification_type_display()}'


class RoleNotificationSetting(models.Model):
    role = models.ForeignKey(
        'role_management.Role',
        on_delete=models.CASCADE,
        related_name='notification_settings',
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationPreference.NotificationType.choices,
    )
    enabled = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['role', 'notification_type'],
                name='unique_role_notification_type',
            ),
        ]
        ordering = ('notification_type',)

    def __str__(self):
        return f'{self.role.group.name} - {self.get_notification_type_display()}'


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
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
        ordering = ('-created_at',)
        indexes = [
            models.Index(
                fields=['user', 'is_read', '-created_at'],
                name='notif_user_read_date_idx',
            ),
            models.Index(
                fields=['user', '-created_at'],
                name='notif_user_date_idx',
            ),
            models.Index(
                fields=['user', 'notification_type', 'is_read'],
                name='notif_user_type_read_idx',
            ),
        ]

    def __str__(self):
        return f'{self.user.email} - {self.title}'


NOTIFICATION_TYPE_DESCRIPTIONS = {
    NotificationPreference.NotificationType.NEW_DOCUMENT_SUBMITTED: (
        'Receive an alert when a faculty member submits a new document.'
    ),
    NotificationPreference.NotificationType.DOCUMENT_RESUBMITTED: (
        'Receive an alert when a faculty member resubmits a document.'
    ),
    NotificationPreference.NotificationType.ALL_REQUIREMENTS_COMPLETED: (
        'Receive an alert when a faculty member completes all required documents.'
    ),
    NotificationPreference.NotificationType.SUBMISSION_UNDER_REVIEW: (
        'Receive an update when your document submission enters review.'
    ),
    NotificationPreference.NotificationType.SUBMISSION_REVIEWED: (
        'Receive an update when your document has been reviewed and awaits approval.'
    ),
    NotificationPreference.NotificationType.SUBMISSION_NEEDS_REVISION: (
        'Receive an update when your document is returned for revision.'
    ),
    NotificationPreference.NotificationType.SUBMISSION_APPROVED: (
        'Receive an update when your document submission is approved.'
    ),
    NotificationPreference.NotificationType.REQUIREMENTS_OPENED: (
        'Receive an alert when requirements assigned to you become available.'
    ),
    NotificationPreference.NotificationType.DEADLINE_CHANGED: (
        'Receive an alert when the deadline for your assigned requirements changes.'
    ),
    NotificationPreference.NotificationType.ACCOUNT_LOCKED_OUT: (
        'Receive an alert when an account is locked after repeated failed sign-in attempts.'
    ),
    NotificationPreference.NotificationType.NEW_LOGIN: (
        'Receive an alert when an unfamiliar device or browser accesses your account.'
    ),
    NotificationPreference.NotificationType.SYSTEM_ANNOUNCEMENT: (
        'Receive system-wide announcements from the iSubmit administrators.'
    ),
}


# These audiences control which event switches are shown for each role.
# They do not grant application permissions.
NOTIFICATION_TYPE_AUDIENCES = {
    NotificationPreference.NotificationType.NEW_DOCUMENT_SUBMITTED: 'ADMIN',
    NotificationPreference.NotificationType.DOCUMENT_RESUBMITTED: 'ADMIN',
    NotificationPreference.NotificationType.ALL_REQUIREMENTS_COMPLETED: 'ADMIN',
    NotificationPreference.NotificationType.ACCOUNT_LOCKED_OUT: 'ADMIN',

    NotificationPreference.NotificationType.SUBMISSION_UNDER_REVIEW: 'FACULTY',
    NotificationPreference.NotificationType.SUBMISSION_REVIEWED: 'FACULTY',
    NotificationPreference.NotificationType.SUBMISSION_NEEDS_REVISION: 'FACULTY',
    NotificationPreference.NotificationType.SUBMISSION_APPROVED: 'FACULTY',
    NotificationPreference.NotificationType.REQUIREMENTS_OPENED: 'FACULTY',
    NotificationPreference.NotificationType.DEADLINE_CHANGED: 'FACULTY',

    NotificationPreference.NotificationType.NEW_LOGIN: 'ALL',
    NotificationPreference.NotificationType.SYSTEM_ANNOUNCEMENT: 'ALL',
}

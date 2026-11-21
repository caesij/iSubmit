from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase

from notifications.models import (
    NOTIFICATION_TYPE_AUDIENCES,
    NOTIFICATION_TYPE_DESCRIPTIONS,
    Notification,
    NotificationPreference,
    RoleNotificationSetting,
)
from notifications.services import (
    ensure_default_role_notification_settings,
    notify_role_subscribers,
    notify_user,
)
from role_management.models import Role
from role_management.services import ensure_default_roles

User = get_user_model()
NotificationType = NotificationPreference.NotificationType


class NotificationDeliveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ensure_default_roles()
        ensure_default_role_notification_settings()

        cls.admin_role = Role.objects.get(code=Role.Code.ADMIN, is_default=True)
        cls.staff_role = Role.objects.get(code=Role.Code.STAFF, is_default=True)
        cls.faculty_role = Role.objects.get(code=Role.Code.FACULTY, is_default=True)

    def create_user(self, email, role, employee_id):
        return User.objects.create_user(
            email=email,
            password='Test-password-123!',
            role=role,
            first_name='Test',
            middle_name='',
            last_name='User',
            employee_ID=employee_id,
        )

    @patch('notifications.services.send_mass_mail')
    @patch('notifications.services.send_to_user')
    def test_submission_status_notification_goes_only_to_uploader(
        self,
        mock_send_to_user,
        mock_send_mass_mail,
    ):
        uploader = self.create_user(
            'uploader@example.com', self.faculty_role, 'TEST-001'
        )
        other_faculty = self.create_user(
            'other@example.com', self.faculty_role, 'TEST-002'
        )

        with self.captureOnCommitCallbacks(execute=True):
            delivered = notify_user(
                uploader,
                NotificationType.SUBMISSION_APPROVED,
                'Submission Approved',
                'Your document was approved.',
                send_email_notification=False,
            )

        self.assertEqual(delivered, 1)
        self.assertTrue(
            Notification.objects.filter(
                user=uploader,
                notification_type=NotificationType.SUBMISSION_APPROVED,
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                user=other_faculty,
                notification_type=NotificationType.SUBMISSION_APPROVED,
            ).exists()
        )
        mock_send_to_user.assert_called_once()
        mock_send_mass_mail.assert_not_called()

    @patch('notifications.services.send_mass_mail')
    @patch('notifications.services.send_to_user')
    def test_upload_alert_targets_only_roles_subscribed_to_event(
        self,
        mock_send_to_user,
        mock_send_mass_mail,
    ):
        admin = self.create_user(
            'admin@example.com', self.admin_role, 'TEST-003'
        )
        staff = self.create_user(
            'staff@example.com', self.staff_role, 'TEST-004'
        )
        faculty = self.create_user(
            'faculty@example.com', self.faculty_role, 'TEST-005'
        )

        with self.captureOnCommitCallbacks(execute=True):
            delivered = notify_role_subscribers(
                NotificationType.NEW_DOCUMENT_SUBMITTED,
                'New Document Submission',
                'A faculty member submitted a document.',
                send_email_notification=False,
            )

        self.assertEqual(delivered, 2)
        self.assertEqual(
            set(Notification.objects.values_list('user_id', flat=True)),
            {admin.pk, staff.pk},
        )
        self.assertFalse(
            Notification.objects.filter(user=faculty).exists()
        )
        self.assertEqual(mock_send_to_user.call_count, 2)
        mock_send_mass_mail.assert_not_called()

    @patch('notifications.services.send_mass_mail')
    @patch('notifications.services.send_to_user')
    def test_disabled_personal_preference_blocks_delivery(
        self,
        mock_send_to_user,
        mock_send_mass_mail,
    ):
        admin = self.create_user(
            'disabled-admin@example.com', self.admin_role, 'TEST-006'
        )
        NotificationPreference.objects.create(
            user=admin,
            notification_type=NotificationType.NEW_DOCUMENT_SUBMITTED,
            enabled=False,
        )

        with self.captureOnCommitCallbacks(execute=True):
            delivered = notify_role_subscribers(
                NotificationType.NEW_DOCUMENT_SUBMITTED,
                'New Document Submission',
                'A faculty member submitted a document.',
            )

        self.assertEqual(delivered, 0)
        self.assertFalse(Notification.objects.filter(user=admin).exists())
        mock_send_to_user.assert_not_called()
        mock_send_mass_mail.assert_not_called()

    @patch('notifications.services.send_mass_mail')
    @patch('notifications.services.send_to_user')
    def test_custom_role_can_subscribe_without_an_application_permission(
        self,
        mock_send_to_user,
        mock_send_mass_mail,
    ):
        group = Group.objects.create(name='Document Monitoring')
        custom_role = Role.objects.create(group=group, is_default=False)
        monitor = self.create_user(
            'monitor@example.com', custom_role, 'TEST-007'
        )
        RoleNotificationSetting.objects.create(
            role=custom_role,
            notification_type=NotificationType.DOCUMENT_RESUBMITTED,
            enabled=True,
        )

        with self.captureOnCommitCallbacks(execute=True):
            delivered = notify_role_subscribers(
                NotificationType.DOCUMENT_RESUBMITTED,
                'Document Resubmitted',
                'A faculty member resubmitted a document.',
                send_email_notification=False,
            )

        self.assertEqual(delivered, 1)
        self.assertTrue(Notification.objects.filter(user=monitor).exists())
        mock_send_to_user.assert_called_once()
        mock_send_mass_mail.assert_not_called()

    def test_every_notification_event_has_an_audience(self):
        event_values = {value for value, _ in NotificationType.choices}
        self.assertEqual(event_values, set(NOTIFICATION_TYPE_AUDIENCES))
        self.assertEqual(event_values, set(NOTIFICATION_TYPE_DESCRIPTIONS))

    def test_default_settings_initialization_does_not_overwrite_manual_changes(self):
        setting = RoleNotificationSetting.objects.get(
            role=self.admin_role,
            notification_type=NotificationType.NEW_DOCUMENT_SUBMITTED,
        )
        setting.enabled = False
        setting.save(update_fields=['enabled'])

        ensure_default_role_notification_settings()

        setting.refresh_from_db()
        self.assertFalse(setting.enabled)

    @patch('notifications.services.send_mass_mail')
    @patch('notifications.services.send_to_user')
    def test_role_level_setting_blocks_direct_user_notification(
        self,
        mock_send_to_user,
        mock_send_mass_mail,
    ):
        faculty = self.create_user(
            'no-status-alert@example.com', self.faculty_role, 'TEST-008'
        )
        RoleNotificationSetting.objects.filter(
            role=self.faculty_role,
            notification_type=NotificationType.SUBMISSION_APPROVED,
        ).update(enabled=False)

        with self.captureOnCommitCallbacks(execute=True):
            delivered = notify_user(
                faculty,
                NotificationType.SUBMISSION_APPROVED,
                'Submission Approved',
                'Your document was approved.',
            )

        self.assertEqual(delivered, 0)
        self.assertFalse(Notification.objects.filter(user=faculty).exists())
        mock_send_to_user.assert_not_called()
        mock_send_mass_mail.assert_not_called()


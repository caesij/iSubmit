from django.db.models.signals import post_migrate
from django.dispatch import receiver

from notifications.services import ensure_default_role_notification_settings


@receiver(post_migrate)
def initialize_default_role_notification_settings(sender, **kwargs):
    if sender.label != 'notifications':
        return

    ensure_default_role_notification_settings()

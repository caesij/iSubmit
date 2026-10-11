import hashlib
import secrets

from datetime import timedelta

from axes.helpers import get_client_ip_address
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityLoginRecord
from notifications.models import NotificationPreference
from notifications.services import create_notif


DEVICE_COOKIE_NAME = 'isubmit_trusted_devices'
DEVICE_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
TRUST_PERIOD = timedelta(days=30)


def assess_login_security(request, user):
    now = timezone.now()
    ip_address = (get_client_ip_address(request) or 'unknown')[:45]
    user_agent = (request.META.get('HTTP_USER_AGENT') or 'Unknown browser/device')[:255]
    device_token = request.COOKIES.get(DEVICE_COOKIE_NAME)

    if not isinstance(device_token, str) or not (32 <= len(device_token) <= 128):
        device_token = secrets.token_urlsafe(32)

    device_token_hash = hashlib.sha256(device_token.encode('utf-8')).hexdigest()

    expires_at = now + TRUST_PERIOD

    with transaction.atomic():
        record, created = SecurityLoginRecord.objects.get_or_create(
            user=user,
            device_token_hash=device_token_hash,
            ip_address=ip_address,
            defaults={
                'user_agent': user_agent,
                'last_seen': now,
                'expires_at': expires_at,
            }
        )

        should_alert = created or record.expires_at <= now

        record.user_agent = user_agent
        record.last_seen = now
        record.expires_at = expires_at
        record.save(
            update_fields=[
                'user_agent',
                'last_seen',
                'expires_at'
            ]
        )

        SecurityLoginRecord.objects.filter(
            user=user,
            expires_at__lte=now
        ).exclude(pk=record.pk).delete()

    return {
        'device_token': device_token,
        'ip_address': ip_address,
        'user_agent': user_agent,
        'login_time': timezone.localtime(now).strftime(
            '%b %d, %Y at %I:%M %p'
        ),
        'should_alert': should_alert
    }


def send_login_security_alert(user, login_info):
    if not login_info['should_alert']:
        return None

    return create_notif(
        user=user,
        notification_type=(NotificationPreference.NotificationType.SECURITY_ALERTS),
        title="New login to your iSubmit account",
        message=(
            "A browser/IP combination not seen together on your "
            "account within the last 30 days was used to log in.\n\n"
            f"Login time: {login_info['login_time']}\n"
            f"IP address: {login_info['ip_address']}\n"
            f"Browser/device: {login_info['user_agent']}\n\n"
            "If you do not recognize this login, change your password "
            "and contact your system administrator."
        ),
        link=reverse("notifications:notification_list")
    )
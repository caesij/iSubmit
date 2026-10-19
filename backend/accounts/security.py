import hashlib
import secrets

from datetime import timedelta

from django.db import transaction
from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone

from accounts.models import SecurityLoginRecord
from core.realtime import send_to_session, send_to_user
from core.date_formatting import format_display_date, format_display_time
from notifications.models import NotificationPreference
from notifications.services import create_notif


DEVICE_COOKIE_NAME = 'isubmit_trusted_devices'
DEVICE_COOKIE_MAX_AGE = 30 * 24 * 60 * 60
TRUST_PERIOD = timedelta(days=30)


def get_login_activity(user, current_session_key):
    now = timezone.now()
    active_session_keys = set(
        Session.objects.filter(expire_date__gt=now)
        .values_list('session_key', flat=True)
    )
    SecurityLoginRecord.objects.filter(user=user).exclude(
        session_key__in=active_session_keys
    ).delete()
    records = SecurityLoginRecord.objects.filter(
        user=user,
        expires_at__gt=now,
        session_key__in=active_session_keys,
    ).order_by('-last_seen')
    return [
        {
            'record': record,
            'device': record.user_agent or 'Unknown browser/device',
            'is_current': record.session_key == current_session_key
        }
        for record in records
    ]


def revoke_login_record(user, record_id, current_session_key):
    with transaction.atomic():
        record = SecurityLoginRecord.objects.select_for_update().filter(id=record_id, user=user).first()
        if not record:
            return False

        is_current = record.session_key == current_session_key
        if record.session_key:
            send_to_session(record.session_key, 'security.session-revoked')
            Session.objects.filter(session_key=record.session_key).delete()
        record.delete()
        transaction.on_commit(
            lambda: send_to_user(user, 'security.activity-updated')
        )
        return is_current


def revoke_current_login(user, current_session_key):
    record_id = SecurityLoginRecord.objects.filter(
        user=user,
        session_key=current_session_key,
    ).values_list('id', flat=True).first()
    if record_id:
        revoke_login_record(user, record_id, current_session_key)


def revoke_other_logins(user, current_session_key):
    with transaction.atomic():
        records = SecurityLoginRecord.objects.select_for_update().filter(
            user=user,
        ).exclude(session_key=current_session_key)
        session_keys = list(
            records.exclude(session_key__isnull=True)
            .values_list('session_key', flat=True)
        )
        if session_keys:
            for session_key in session_keys:
                send_to_session(session_key, 'security.session-revoked')
            Session.objects.filter(session_key__in=session_keys).delete()
        records.delete()
        transaction.on_commit(
            lambda: send_to_user(user, 'security.activity-updated')
        )


def assess_login_security(request, user):
    now = timezone.now()
    user_agent = (request.META.get('HTTP_USER_AGENT') or 'Unknown browser/device')[:255]
    session_key = request.session.session_key
    device_token = request.COOKIES.get(DEVICE_COOKIE_NAME)

    if not isinstance(device_token, str) or not (32 <= len(device_token) <= 128):
        device_token = secrets.token_urlsafe(32)

    device_token_hash = hashlib.sha256(device_token.encode('utf-8')).hexdigest()

    expires_at = now + TRUST_PERIOD

    with transaction.atomic():
        record, created = SecurityLoginRecord.objects.get_or_create(
            user=user,
            device_token_hash=device_token_hash,
            session_key=session_key,
            defaults={
                'user_agent': user_agent,
                'last_seen': now,
                'expires_at': expires_at
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

    transaction.on_commit(
        lambda: send_to_user(user, 'security.activity-updated')
    )

    return {
        'device_token': device_token,
        'user_agent': user_agent,
        'login_time': (
            f'{format_display_date(now)} at {format_display_time(now)}'
        ),
        'should_alert': should_alert
    }


def send_login_security_alert(user, login_info):
    if not login_info['should_alert']:
        return None

    return create_notif(
        user=user,
        notification_type=(NotificationPreference.NotificationType.SECURITY_NOTIFICATIONS),
        title="New login to your iSubmit account",
        message=(
            "A browser or device not seen on your account within the "
            "last 30 days was used to log in.\n\n"
            f"Login time: {login_info['login_time']}\n"
            f"Browser/device: {login_info['user_agent']}\n\n"
            "If you do not recognize this login, change your password "
            "and contact your system administrator."
        ),
        link=reverse('faculty_portal:account_security' if user.is_faculty else 'admin_staff_portal:account_security')
    )
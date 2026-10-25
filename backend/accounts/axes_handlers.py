import logging
from math import ceil

from axes.handlers.database import AxesDatabaseHandler
from axes.helpers import get_client_username, get_cool_off
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


def lockout_response(request, original_response=None, credentials=None):
    credentials = credentials or {}
    username = get_client_username(request, credentials) or ''

    remaining_seconds = 0
    cooloff = get_cool_off(request)

    if cooloff is not None:
        try:
            handler = AxesDatabaseHandler()
            attempt_times = []

            for attempts in handler.get_user_attempts(request, credentials):
                attempt_time = (
                    attempts.order_by('-attempt_time')
                    .values_list('attempt_time', flat=True)
                    .first()
                )

                if attempt_time is not None:
                    attempt_times.append(attempt_time)

            if attempt_times:
                locked_until = max(attempt_times) + cooloff
                remaining_seconds = max(
                    0,
                    ceil((locked_until - timezone.now()).total_seconds())
                )

        except Exception:
            logger.exception('Could not calculate the remaining login lockout time.')
            
    context = {
        'username': username,
        'remaining_seconds': remaining_seconds
    }

    response = render(request, 'accounts/lockout.html', context, status=403)

    if remaining_seconds > 0:
        response['Retry-After'] = str(remaining_seconds)

    return response
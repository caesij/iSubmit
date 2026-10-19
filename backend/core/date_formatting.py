from datetime import date, datetime

from django.utils import timezone
from django.utils.formats import date_format


def _localize(value):
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return timezone.localtime(value)

    return value


def format_display_date(value):
    if not value:
        return ''

    return date_format(_localize(value), 'M j, Y')


def format_display_time(value):
    if not value:
        return ''

    if isinstance(value, date) and not isinstance(value, datetime):
        return ''

    return date_format(_localize(value), 'g:i A')

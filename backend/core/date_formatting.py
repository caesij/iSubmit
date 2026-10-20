from datetime import date, datetime

from django.utils import timezone
from django.utils.formats import date_format


def _localize(value):
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_current_timezone())
        return timezone.localtime(value)

    return value


def format_display_date(value, user=None):
    if not value:
        return ''

    date_format_value = getattr(user, 'date_format', 'F j, Y')
    return date_format(_localize(value), date_format_value)


def format_display_time(value, user=None):
    if not value:
        return ''

    if isinstance(value, date) and not isinstance(value, datetime):
        return ''

    time_format_value = (
        'H:i'
        if getattr(user, 'time_format', '12') == '24'
        else 'g:i A'
    )
    return date_format(_localize(value), time_format_value)

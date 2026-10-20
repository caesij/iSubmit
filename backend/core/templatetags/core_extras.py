from django import template

from core.date_formatting import format_display_date, format_display_time

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    return getattr(obj, attr_name, False)


@register.filter
def display_date(value, user=None):
    return format_display_date(value, user)


@register.filter
def display_time(value, user=None):
    return format_display_time(value, user)
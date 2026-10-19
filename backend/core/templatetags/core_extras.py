from django import template

from core.date_formatting import format_display_date, format_display_time

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    return getattr(obj, attr_name, False)


@register.filter
def display_date(value):
    return format_display_date(value)


@register.filter
def display_time(value):
    return format_display_time(value)
import logging

from django.urls import reverse
from core.date_formatting import format_display_date

from admin_staff_portal.realtime import (
    refresh_admin_dashboard,
    refresh_staff_dashboard,
    refresh_submission_pages,
)
from faculty_portal.realtime import (
    refresh_all_faculty_submission_bins,
    refresh_faculty_dashboard,
)
from notifications.models import NotificationPreference
from notifications.services import notify_users
from submissions.helpers import get_target_faculty_queryset
from submissions.models import Requirement, active_q

logger = logging.getLogger(__name__)
NotificationType = NotificationPreference.NotificationType

NOTICES = {
    'created': (
        NotificationType.REQUIREMENTS_OPENED,
        'New Submission Requirements',
        'Requirements for {period} are now open. Deadline: {deadline}.',
    ),
    'deadline_changed': (
        NotificationType.DEADLINE_CHANGED,
        'Submission Deadline Updated',
        'The deadline for {period} is now {deadline}.',
    ),
}


def save_requirements(period, rows):
    saved_ids = set(period.requirements.values_list('pk', flat=True))

    requirements = [
        Requirement(
            id=row['id'] if row['id'] in saved_ids else None,
            period=period,
            order=position,
            status=(
                Requirement.ReqStatus.ACTIVE
                if row['include']
                else Requirement.ReqStatus.INACTIVE
            ),
            **{field: row[field] for field in Requirement.SETTING_FIELDS},
        )
        for position, row in enumerate(rows)
        if row
    ]

    Requirement.objects.bulk_create(
        requirements,
        update_conflicts=True,
        unique_fields=['id'],
        update_fields=[*Requirement.SETTING_FIELDS, 'order', 'status', 'updated_at'],
    )


def publish_updates(period=None, notice=None):
    try:
        refresh_admin_dashboard()
        refresh_staff_dashboard()
        refresh_submission_pages()
        refresh_all_faculty_submission_bins()
    except Exception:
        logger.exception('Could not refresh dashboards after requirement updates.')

    faculty_queryset = get_target_faculty_queryset()

    if period is not None and notice in NOTICES:
        faculty_queryset = faculty_queryset.filter(
            upload_slots__requirement__period=period,
        ).filter(
            active_q('upload_slots__requirement__')
        ).distinct()

    faculty_members = list(faculty_queryset)

    for faculty in faculty_members:
        try:
            refresh_faculty_dashboard(faculty)
        except Exception:
            logger.exception(
                'Could not refresh the faculty dashboard for user %s.',
                faculty.pk,
            )

    notice_details = NOTICES.get(notice)
    if not notice_details or not faculty_members:
        return

    notification_type, title, message_template = notice_details

    try:
        notify_users(
            faculty_members,
            notification_type=notification_type,
            title=title,
            message=lambda faculty: message_template.format(
                period=period,
                deadline=format_display_date(period.deadline, faculty),
            ),
            link=reverse('faculty_portal:upload_files'),
        )
    except Exception:
        logger.exception('Could not send requirement notifications.')

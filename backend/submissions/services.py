import logging

from django.urls import reverse
from core.date_formatting import format_display_date

from admin_staff_portal.realtime import (
    refresh_admin_dashboard,
    refresh_staff_dashboard,
    refresh_submission_pages
)

from faculty_portal.realtime import refresh_all_faculty_submission_bins, refresh_faculty_dashboard

from notifications.models import NotificationPreference
from notifications.services import create_notif
from submissions.helpers import get_target_faculty_queryset
from submissions.models import Requirement

logger = logging.getLogger(__name__)

NOTICES = {
    'created': (
        'New Submission Requirements',
        'Requirements for {period} are now open. Deadline: {deadline}.'
    ),
    'deadline_changed': (
        'Submission Deadline Updated',
        'The deadline for {period} is now {deadline}.'
    )
}


def save_requirements(period, rows):
    saved_ids = set(period.requirements.values_list('pk', flat=True))

    requirements = [
        Requirement(
            id=row['id'] if row['id'] in saved_ids else None,
            period=period,
            order=position,
            status=Requirement.ReqStatus.ACTIVE if row['include'] else Requirement.ReqStatus.INACTIVE,
            **{field: row[field] for field in Requirement.SETTING_FIELDS}
        )
        for position, row in enumerate(rows)
        if row
    ]

    Requirement.objects.bulk_create(
        requirements,
        update_conflicts=True,
        unique_fields=['id'],
        update_fields=[*Requirement.SETTING_FIELDS, 'order', 'status', 'updated_at']
    )


def publish_updates(period=None, notice=None):
    title, message = NOTICES.get(notice, (None, None))

    try:
        refresh_admin_dashboard()
        refresh_staff_dashboard()
        refresh_submission_pages()
        refresh_all_faculty_submission_bins()

        for faculty in get_target_faculty_queryset():
            refresh_faculty_dashboard(faculty)

            if title:
                create_notif(
                    user=faculty,
                    notification_type=NotificationPreference.NotificationType.SYSTEM_NOTIFICATIONS,
                    title=title,
                    message=message.format(
                        period=period,
                        deadline=format_display_date(period.deadline, faculty),
                    ),
                    link=reverse('faculty_portal:upload_files'),
                )
    except Exception:
        logger.exception('Could not publish requirement updates')

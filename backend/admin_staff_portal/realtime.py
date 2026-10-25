from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from core.realtime import send_to_group


def refresh_submission_pages(data=None):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        'admin_staff_submissions',
        {
            'type': 'realtime_event',
            'event': 'submissions.update',
            'data': data or {},
        },
    )


def refresh_admin_dashboard():
    channel_layer = get_channel_layer()
    
    try:
        async_to_sync(channel_layer.group_send)(
            'admin_dashboard',
            {
                'type': 'realtime_event',
                'event': 'admin-dashboard.update',
                'data': {},
            },
        )
    except Exception as e:
        print('ADMIN DASHBOARD REALTIME ERROR', repr(e))


def refresh_staff_dashboard():
    channel_layer = get_channel_layer()

    try:
        async_to_sync(channel_layer.group_send)(
            'staff_dashboard',
            {
                'type': 'realtime_event',
                'event': 'staff-dashboard.update',
                'data': {},
            },
        )
    except Exception as e:
        print('STAFF DASHBOARD REALTIME ERROR:', repr(e))


def refresh_document_surfaces(faculty_ids):
    faculty_ids = [str(faculty_id) for faculty_id in set(faculty_ids)]
    data = {'faculty_ids': faculty_ids}

    refresh_submission_pages(data)
    refresh_admin_dashboard()
    refresh_staff_dashboard()

    for faculty_id in faculty_ids:
        send_to_group(f'user_{faculty_id}', 'documents.update', data)
        send_to_group(f'user_{faculty_id}', 'dashboard.update', data)
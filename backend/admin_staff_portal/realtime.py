from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


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
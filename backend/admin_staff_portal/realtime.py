from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def refresh_admin_dashboard():
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        'admin_dashboard',
        {
            'type': 'realtime_event',
            'event': 'dashboard.update',
            'data': {},
        },
    )
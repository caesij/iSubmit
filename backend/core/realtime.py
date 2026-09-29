from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def send_to_user(user, event, data=None):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        f'user_{user.pk}',
        {
            'type': 'realtime_event',
            'event': event,
            'data': data or {},
        },
    )

def send_to_group(group_name, event, data=None):
    channel_layer = get_channel_layer()

    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'realtime_event',
            'event': event,
            'data': data or {},
        },
    )
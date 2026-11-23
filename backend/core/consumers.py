import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer


logger = logging.getLogger(__name__)

REALTIME_GROUP_PERMISSIONS = {
    'faculty_submission_bins': 'accounts.access_faculty_submission_bin',
    'admin_dashboard': 'accounts.access_admin_dashboard',
    'staff_dashboard': 'accounts.access_staff_dashboard',
    'admin_staff_submissions': 'accounts.access_faculty_submissions',
}


@database_sync_to_async
def get_realtime_groups(user):
    if user.is_superuser:
        return tuple(REALTIME_GROUP_PERMISSIONS.keys())

    return tuple(
        group_name
        for group_name, permission in REALTIME_GROUP_PERMISSIONS.items()
        if user.has_perm(permission)
    )


# WebSocket consumer
class RealtimeConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        self.joined_groups = []

        user = self.scope.get('user')

        # Only authenticated and active users can establish a connection
        if not user or not user.is_authenticated or not user.is_active:
            await self.close()
            return

        # User-specific group
        await self.join_group(f'user_{user.pk}')

        # Session-specific group
        session = self.scope.get('session')
        session_key = session.session_key if session else None

        if session_key:
            await self.join_group(f'session_{session_key}')

        # Permission-based groups
        authorized_groups = await get_realtime_groups(user)

        for group_name in authorized_groups:
            await self.join_group(group_name)

        await self.accept()

    async def disconnect(self, close_code):
        for group_name in getattr(self, 'joined_groups', []):
            try:
                await self.channel_layer.group_discard(
                    group_name,
                    self.channel_name,
                )
            except Exception:
                logger.exception(
                    'Could not remove WebSocket connection from group %s.',
                    group_name,
                )

        self.joined_groups = []

    async def join_group(self, group_name):
        await self.channel_layer.group_add(
            group_name,
            self.channel_name,
        )

        self.joined_groups.append(group_name)

    # Event handling
    async def realtime_event(self, event):
        await self.send_json({
            'event': event['event'],
            'data': event.get('data', {}),
        })

    async def receive_json(self, content, **kwargs):
        pass

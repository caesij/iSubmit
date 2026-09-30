from channels.generic.websocket import AsyncJsonWebsocketConsumer


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope['user']

        if user.is_anonymous:
            await self.close()
            return

        self.group_name = f'user_{user.pk}'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        if user.role == user.Role.ADMIN:
            await self.channel_layer.group_add(
                'admin_dashboard',
                self.channel_name,
            )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

        user = self.scope.get('user')

        if (
            user
            and not user.is_anonymous
            and user.role == user.Role.ADMIN
        ):
            await self.channel_layer.group_discard(
                'admin_dashboard',
                self.channel_name,
            )

    async def realtime_event(self, event):
        await self.send_json({
            'event': event['event'],
            'data': event.get('data', {}),
        })

    async def receive_json(self, content, **kwargs):
        pass
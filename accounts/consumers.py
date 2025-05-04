from channels.generic.websocket import AsyncWebsocketConsumer
import json
from channels.db import database_sync_to_async
from accounts.models import CustomUser

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs']['user_id']
        self.user = await self.get_user(self.user_id)
        
        if not self.user:
            await self.close()
            return

        self.group_name = f'notifications_{self.user_id}'

        # Add user to the group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        # Handle any incoming messages if needed (optional)
        pass

    async def send_notification(self, event):
        # Send the notification to the WebSocket client
        message = event['message']
        notification_type = event['notification_type']
        await self.send(text_data=json.dumps({
            'message': message,
            'type': notification_type,
        }))

    @database_sync_to_async
    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(userID=user_id)
        except CustomUser.DoesNotExist:
            return None
import json

from channels.generic.websocket import AsyncWebsocketConsumer


class ElectoralResultsConsumer(AsyncWebsocketConsumer):
    group_name = "electoral_results"

    async def connect(self):
        if self.scope.get("user") is None or not self.scope["user"].is_authenticated:
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def electoral_results_updated(self, event):
        await self.send(text_data=json.dumps(event["payload"]))

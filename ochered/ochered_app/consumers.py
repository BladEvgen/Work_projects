import json
import asyncio

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from ochered_app import models


class QueueConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.consultant_id = self.scope["url_route"]["kwargs"].get("consultant_id")
        self.room_group_name = (
            f"queue_{self.consultant_id}" if self.consultant_id else "queue_updates"
        )

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.channel_layer.group_add("queue_updates", self.channel_name)

        self.ping_task = asyncio.create_task(self.send_pings())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard("queue_updates", self.channel_name)

        self.ping_task.cancel()

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data["action"]

        if action == "call_next":
            await self.handle_call_next()
        elif action == "complete_ticket":
            await self.handle_complete_ticket()

    async def handle_call_next(self):
        if self.consultant_id:
            consultant = await sync_to_async(models.Consultant.objects.get)(
                pk=self.consultant_id
            )
            current_ticket = await sync_to_async(
                models.Ticket.objects.filter(
                    status="in_progress", consultant=consultant
                ).first
            )()

            if not current_ticket:
                next_ticket = await sync_to_async(
                    models.Ticket.objects.filter(status="waiting")
                    .order_by("number")
                    .first
                )()

                if next_ticket:
                    next_ticket.status = "in_progress"
                    next_ticket.consultant = consultant
                    await sync_to_async(next_ticket.save)()

                    await self.channel_layer.group_send(
                        "queue_updates",
                        {
                            "type": "broadcast_call_next_ticket",
                            "ticket_number": next_ticket.number,
                            "consultant_id": self.consultant_id,
                            "table_number": consultant.table_number,
                        },
                    )

    async def handle_complete_ticket(self):
        if self.consultant_id:
            consultant = await sync_to_async(models.Consultant.objects.get)(
                pk=self.consultant_id
            )
            current_ticket = await sync_to_async(
                models.Ticket.objects.filter(
                    status="in_progress", consultant=consultant
                ).first
            )()

            if current_ticket:
                current_ticket.status = "served"
                await sync_to_async(current_ticket.save)()

                await self.channel_layer.group_send(
                    "queue_updates",
                    {
                        "type": "broadcast_complete_current_ticket",
                        "ticket_number": current_ticket.number,
                        "consultant_id": self.consultant_id,
                    },
                )

    async def new_ticket(self, event):
        ticket_number = event["ticket_number"]

        await self.send(
            text_data=json.dumps(
                {"ticket_number": ticket_number, "action": "new_ticket"}
            )
        )

    async def broadcast_call_next_ticket(self, event):
        ticket_number = event["ticket_number"]
        consultant_id = event["consultant_id"]
        table_number = event["table_number"]

        await self.send(
            text_data=json.dumps(
                {
                    "ticket_number": ticket_number,
                    "consultant_id": consultant_id,
                    "table_number": table_number,
                    "action": "call_next",
                }
            )
        )

    async def broadcast_complete_current_ticket(self, event):
        ticket_number = event["ticket_number"]
        consultant_id = event["consultant_id"]

        await self.send(
            text_data=json.dumps(
                {
                    "ticket_number": ticket_number,
                    "consultant_id": consultant_id,
                    "action": "complete_ticket",
                }
            )
        )

    async def send_pings(self):
        while True:
            try:
                await self.send(text_data=json.dumps({"type": "ping"}))
                await asyncio.sleep(120)
            except asyncio.CancelledError:
                break

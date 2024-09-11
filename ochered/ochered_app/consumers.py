import json
import asyncio
from ochered_app import models
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class QueueConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for handling queue-related events in real-time.

    This consumer manages tickets in a queue, allows consultants to call the
    next ticket, mark a ticket as complete, transfer a ticket to another
    consultant, and handle the case where a visitor did not show up.
    """

    async def connect(self):
        """Handles the initial WebSocket connection.

        Retrieves the consultant ID from the URL, joins the appropriate
        WebSocket group, and starts a periodic ping task to keep the connection alive.

        The consultant's group name is used to route specific updates to the correct WebSocket connection.
        """
        self.consultant_id = self.scope["url_route"]["kwargs"].get("consultant_id")
        self.room_group_name = (
            f"queue_{self.consultant_id}" if self.consultant_id else "queue_updates"
        )
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        await self.channel_layer.group_add("queue_updates", self.channel_name)
        self.ping_task = asyncio.create_task(self.send_pings())

    async def disconnect(self, close_code):
        """Handles WebSocket disconnection.

        Removes the consumer from the WebSocket group and cancels the ping task.

        Args:
            close_code (int): The WebSocket close code indicating the reason for disconnection.
        """
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        await self.channel_layer.group_discard("queue_updates", self.channel_name)
        self.ping_task.cancel()

    async def receive(self, text_data):
        """Handles incoming WebSocket messages.

        Processes different actions such as `call_next`, `complete_ticket`,
        `transfer_ticket`, `new_ticket`, and `no_visitor`.

        Args:
            text_data (str): The incoming WebSocket message in JSON format.
        """
        data = json.loads(text_data)
        action = data["action"]
        if action == "call_next":
            await self.handle_call_next()
        elif action == "complete_ticket":
            await self.handle_complete_ticket()
        elif action == "transfer_ticket":
            await self.handle_transfer_ticket(data)
        elif action == "cancel_transfer":
            await self.handle_cancel_transfer(data)
        elif action == "new_ticket":
            await self.handle_new_ticket(data["ticket_number"])
        elif action == "no_visitor":
            await self.handle_no_visitor(data)

    async def handle_new_ticket(self, ticket_number):
        """Broadcasts a new ticket to all connected clients.

        Args:
            ticket_number (int): The ticket number for the new ticket.
        """
        await self.channel_layer.group_send(
            "queue_updates",
            {
                "type": "broadcast_new_ticket",
                "ticket_number": ticket_number,
            },
        )

    async def handle_call_next(self):
        """Handles the action of calling the next ticket in the queue.

        If no current ticket is in progress, it assigns the next waiting ticket
        to the consultant and broadcasts the update.
        """
        if self.consultant_id:
            consultant = await sync_to_async(models.Consultant.objects.get)(pk=self.consultant_id)
            current_ticket = await sync_to_async(
                models.Ticket.objects.filter(status="in_progress", consultant=consultant).first
            )()

            if not current_ticket:
                next_ticket = await sync_to_async(
                    models.Ticket.objects.filter(status="waiting", redirected_to=consultant)
                    .order_by("number")
                    .exclude(status="served")
                    .first
                )()

                if not next_ticket:
                    next_ticket = await sync_to_async(
                        models.Ticket.objects.filter(status="waiting", redirected_to__isnull=True)
                        .order_by("number")
                        .exclude(status="served")
                        .first
                    )()

                if next_ticket:
                    next_ticket.status = "in_progress"
                    next_ticket.consultant = consultant
                    next_ticket.redirected_to = None
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
        """Marks the current ticket as complete and broadcasts the update."""
        if self.consultant_id:
            consultant = await sync_to_async(models.Consultant.objects.get)(pk=self.consultant_id)
            current_ticket = await sync_to_async(
                models.Ticket.objects.filter(status="in_progress", consultant=consultant).first
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

    async def handle_transfer_ticket(self, data):
        """Transfers a ticket to another consultant and broadcasts the update.

        Args:
            data (dict): A dictionary containing `ticket_number` and `new_consultant_id`.
        """
        ticket_number = data.get("ticket_number")
        new_consultant_id = data.get("new_consultant_id")

        if ticket_number and new_consultant_id:
            ticket = await sync_to_async(models.Ticket.objects.get)(number=ticket_number)
            new_consultant = await sync_to_async(models.Consultant.objects.get)(
                pk=new_consultant_id
            )

            if ticket.status != models.Ticket.STATUS_SERVED:
                ticket.redirected_to = new_consultant
                ticket.consultant = None
                ticket.status = models.Ticket.STATUS_WAITING
                await sync_to_async(ticket.save)()

                active_ticket = await sync_to_async(
                    models.Ticket.objects.filter(
                        status="in_progress", consultant=new_consultant
                    ).exists
                )()

                if not active_ticket:
                    ticket.status = models.Ticket.STATUS_IN_PROGRESS
                    ticket.consultant = new_consultant
                    ticket.redirected_to = None
                    await sync_to_async(ticket.save)()

                    await self.channel_layer.group_send(
                        "queue_updates",
                        {
                            "type": "broadcast_call_next_ticket",
                            "ticket_number": ticket.number,
                            "consultant_id": new_consultant_id,
                            "table_number": new_consultant.table_number,
                        },
                    )
                else:
                    await self.channel_layer.group_send(
                        "queue_updates",
                        {
                            "type": "broadcast_transfer_ticket",
                            "ticket_number": ticket.number,
                            "new_consultant_id": new_consultant_id,
                            "previous_consultant_id": self.consultant_id,
                        },
                    )

    async def handle_no_visitor(self, data):
        """Handles the case when a visitor did not show up.

        Marks the ticket as `timeout` and broadcasts the update.

        Args:
            data (dict): A dictionary containing `ticket_number`.
        """
        ticket_number = data.get("ticket_number")
        if ticket_number:
            ticket = await sync_to_async(models.Ticket.objects.get)(number=ticket_number)
            ticket.status = "timeout"
            await sync_to_async(ticket.save)()

            await self.channel_layer.group_send(
                "queue_updates",
                {
                    "type": "broadcast_no_visitor",
                    "ticket_number": ticket_number,
                },
            )

    async def broadcast_new_ticket(self, event):
        """Broadcasts a new ticket to all clients.

        Args:
            event (dict): A dictionary containing `ticket_number`.
        """
        ticket_number = event["ticket_number"]
        await self.send(
            text_data=json.dumps(
                {
                    "ticket_number": ticket_number,
                    "action": "new_ticket",
                }
            )
        )

    async def broadcast_call_next_ticket(self, event):
        """Broadcasts the call for the next ticket.

        Args:
            event (dict): A dictionary containing `ticket_number`, `consultant_id`, and `table_number`.
        """
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
        """Broadcasts the completion of the current ticket.

        Args:
            event (dict): A dictionary containing `ticket_number` and `consultant_id`.
        """
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

    async def broadcast_no_visitor(self, event):
        """Broadcasts that the visitor did not show up (timeout).

        Args:
            event (dict): A dictionary containing `ticket_number`.
        """
        ticket_number = event["ticket_number"]
        await self.send(
            text_data=json.dumps(
                {
                    "ticket_number": ticket_number,
                    "action": "no_visitor",
                }
            )
        )

    async def send_pings(self):
        """Sends periodic ping messages to keep the WebSocket connection alive."""
        while True:
            try:
                await self.send(text_data=json.dumps({"type": "ping"}))
                await asyncio.sleep(120)
            except asyncio.CancelledError:
                break

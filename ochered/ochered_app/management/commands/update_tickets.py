import datetime
from django.utils import timezone
from ochered_app.models import Ticket
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Обновление статусов талонов и удаление талонов с коротким временем ожидания"

    def handle(self, *args, **kwargs):
        self.stdout.write("Начало обновления статусов талонов...")

        now = timezone.now()
        two_hours_ago = now - datetime.timedelta(hours=2)
        one_minute_ago = now - datetime.timedelta(minutes=1)

        channel_layer = get_channel_layer()

        self.update_in_progress_tickets(two_hours_ago, now, channel_layer)

        self.delete_short_duration_tickets(one_minute_ago)

        self.stdout.write("Обновление статусов талонов успешно завершено.")

    def update_in_progress_tickets(self, two_hours_ago, now, channel_layer):
        in_progress_tickets = Ticket.objects.filter(
            status=Ticket.STATUS_IN_PROGRESS, in_progress_at__lte=two_hours_ago
        )

        for ticket in in_progress_tickets:
            if ticket.consultant:
                consultant_id = ticket.consultant.id
                self.stdout.write(
                    f"Обновление статуса талона {ticket.number} на обслужен (консультант: {ticket.consultant.user.username})"
                )
                ticket.status = Ticket.STATUS_SERVED
                ticket.served_at = now
                ticket.save()

                async_to_sync(channel_layer.group_send)(
                    f"queue_{consultant_id}",
                    {
                        "type": "broadcast_complete_current_ticket",
                        "ticket_number": ticket.number,
                        "consultant_id": consultant_id,
                    },
                )
            else:
                self.stdout.write(
                    f"Обновление статуса талона {ticket.number} на обслужен (без консультанта)"
                )
                ticket.status = Ticket.STATUS_SERVED
                ticket.served_at = now
                ticket.save()

    def delete_short_duration_tickets(self, one_minute_ago):
        short_duration_tickets = Ticket.objects.filter(status=Ticket.STATUS_SERVED)

        for ticket in short_duration_tickets:
            if ticket.in_progress_at and ticket.served_at:
                duration = (ticket.served_at - ticket.in_progress_at).total_seconds()
                if duration < 60:
                    consultant_info = (
                        f"консультант: {ticket.consultant.user.username}"
                        if ticket.consultant
                        else "без консультанта"
                    )
                    self.stdout.write(
                        f"Удаление талона {ticket.number} с продолжительностью {duration} секунд ({consultant_info})"
                    )
                    ticket.delete()

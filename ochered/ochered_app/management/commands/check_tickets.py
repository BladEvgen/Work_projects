from django.utils import timezone
from ochered_app.models import Ticket
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Checks tickets and updates their status to timeout if they are older than 60 minutes"

    def handle(self, *args, **kwargs):
        timeout_threshold = timezone.now() - timezone.timedelta(minutes=60)
        tickets_to_timeout = Ticket.objects.filter(
            created_at__lt=timeout_threshold, status="waiting"
        )

        for ticket in tickets_to_timeout:
            ticket.status = "timeout"
            ticket.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {tickets_to_timeout.count()} tickets to timeout"
            )
        )

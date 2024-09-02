from django.core.management.base import BaseCommand
from ochered_app.models import Ticket, TicketStatusHistory

class Command(BaseCommand):
    help = "Очистка всей истории статусов талонов и самих талонов"

    def handle(self, *args, **kwargs):
        TicketStatusHistory.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('История статусов талонов успешно очищена.'))

        Ticket.objects.all().delete()
        self.stdout.write(self.style.SUCCESS('Все талоны успешно очищены.'))

from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django.apps import apps
from django.core.management.color import no_style
from ochered_app.models import Ticket, TicketStatusHistory


class Command(BaseCommand):
    help = "Полная очистка всех талонов и их истории, включая сброс последовательностей для модели Ticket и TicketStatusHistory."

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            TicketStatusHistory.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS("История статусов талонов успешно очищена.")
            )

            Ticket.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("Все талоны успешно очищены."))

            self.reset_sequence("ochered_app", "TicketStatusHistory")
            self.reset_sequence("ochered_app", "Ticket")

    def reset_sequence(self, app_label, model_name):
        model = apps.get_model(app_label, model_name)
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), [model])
        if sequence_sql:
            with connection.cursor() as cursor:
                for command in sequence_sql:
                    cursor.execute(command)
        self.stdout.write(
            self.style.SUCCESS(f"Индексы для {model_name} успешно сброшены.")
        )

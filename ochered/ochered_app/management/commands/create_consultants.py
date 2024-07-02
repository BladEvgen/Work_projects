from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import IntegrityError
from ochered_app.models import Consultant


class Command(BaseCommand):
    help = "Creates consultants and associates them with User objects."

    def add_arguments(self, parser):
        parser.add_argument("count", type=int, help="Number of consultants to create")

    def handle(self, *args, **kwargs):
        count = kwargs["count"]

        if count < 1:
            self.stdout.write(
                self.style.WARNING("Specify a positive count of consultants to create.")
            )
            return

        last_consultant = Consultant.objects.order_by("-table_number").first()

        last_number = last_consultant.table_number if last_consultant else 0

        for i in range(1, count + 1):
            username = f"consultant_{last_number + i}"
            password = "IskyRUCeL"
            first_name = input(f"Enter first name for consultant {i}: ")
            last_name = input(f"Enter last name for consultant {i}: ")

            try:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                Consultant.objects.create(
                    user=user, table_number=get_next_table_number()
                )

                self.stdout.write(self.style.SUCCESS(f"Created consultant {username}"))
            except IntegrityError:
                self.stdout.write(
                    self.style.ERROR(f"Error creating consultant {username}. Skipping.")
                )

        self.stdout.write(
            self.style.SUCCESS(f"Successfully created {count} consultants.")
        )


def get_next_table_number():
    try:
        last_consultant = Consultant.objects.latest("table_number")
        return last_consultant.table_number + 1
    except Consultant.DoesNotExist:
        return 1

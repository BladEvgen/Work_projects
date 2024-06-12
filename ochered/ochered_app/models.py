import uuid
from tabnanny import verbose
from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save


class Consultant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    table_number = models.IntegerField(unique=True)
    class Meta:
        verbose_name = "Консультант"
        verbose_name_plural = "Консультанты"

    def __str__(self) -> str:
        return f"Консультант {self.user.username} за столиком {self.table_number}"


@receiver(post_save, sender=User)
def create_or_update_consultant(sender, instance, created, **kwargs):
    if created:
        consultant, _ = Consultant.objects.get_or_create(
            user=instance, defaults={"table_number": get_next_table_number()}
        )


def get_next_table_number():
    try:
        last_consultant = Consultant.objects.latest("table_number")
        return last_consultant.table_number + 1
    except Consultant.DoesNotExist:
        return 1


class Ticket(models.Model):
    STATUS_CHOICES = [
        ("waiting", "Waiting"),
        ("in_progress", "In progress"),
        ("served", "Served"),
        ("timeout", "Time Out"),
    ]
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    number = models.AutoField(primary_key=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="waiting")
    consultant = models.ForeignKey(
        Consultant, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        verbose_name = "Талон"
        verbose_name_plural = "Талоны"
    def get_status_display(self) -> str:
        for status, display in self.STATUS_CHOICES:
            if status == self.status:
                return display
        return ""

    def __str__(self) -> str:
        return f"Заявка {self.number} - {self.get_status_display()}"

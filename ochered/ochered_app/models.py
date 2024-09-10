import uuid

from django.db import models
from django.utils import timezone
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save


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
        Consultant.objects.get_or_create(
            user=instance, defaults={"table_number": get_next_table_number()}
        )


def get_next_table_number():
    try:
        last_consultant = Consultant.objects.latest("table_number")
        return last_consultant.table_number + 1
    except Consultant.DoesNotExist:
        return 1


class Ticket(models.Model):
    STATUS_WAITING = "waiting"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_SERVED = "served"
    STATUS_TIMEOUT = "timeout"

    STATUS_CHOICES = [
        (STATUS_WAITING, "В ожидании"),
        (STATUS_IN_PROGRESS, "В процессе"),
        (STATUS_SERVED, "Обслужен"),
        (STATUS_TIMEOUT, "Тайм аут"),
    ]

    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    number = models.AutoField(primary_key=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING
    )
    consultant = models.ForeignKey(
        Consultant, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    in_progress_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    redirected_to = models.ForeignKey(
        Consultant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="redirected_tickets",
    )

    class Meta:
        verbose_name = "Талон"
        verbose_name_plural = "Талоны"

    def __str__(self) -> str:
        return f"Заявка {self.number} - {self.get_status_display()}"

    def get_status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, "")


class TicketStatusHistory(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Ticket.STATUS_CHOICES)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "История статусов талона"
        verbose_name_plural = "История статусов талонов"

    def __str__(self) -> str:
        return f"Талон {self.ticket.number} - {self.get_status_display()} на {self.changed_at}"

    def get_status_display(self):
        return dict(Ticket.STATUS_CHOICES).get(self.status, "")


@receiver(pre_save, sender=Ticket)
def update_ticket_status_history(sender, instance, **kwargs):
    if instance.pk:
        previous = Ticket.objects.get(pk=instance.pk)
        if previous.status != instance.status:
            TicketStatusHistory.objects.create(ticket=instance, status=instance.status)

            if (
                instance.status == Ticket.STATUS_IN_PROGRESS
                and not instance.in_progress_at
            ):
                instance.in_progress_at = timezone.now()
            elif instance.status == Ticket.STATUS_SERVED and not instance.served_at:
                instance.served_at = timezone.now()


class AccessLog(models.Model):
    ip = models.CharField(max_length=100)
    device = models.CharField(max_length=100)
    os = models.CharField(max_length=100)
    browser = models.CharField(max_length=100)
    route = models.CharField(max_length=200)
    access_time = models.DateTimeField()

    def __str__(self):
        return f"IP: {self.ip}, Device: {self.device}, OS: {self.os}, Browser: {self.browser}, Route: {self.route}, Access Time: {self.access_time}"

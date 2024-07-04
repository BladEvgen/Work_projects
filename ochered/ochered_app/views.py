import datetime

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import (
    F,
    Q,
    Avg,
    Min,
    Count,
    FloatField,
    DurationField,
    ExpressionWrapper,
)
from django.views import View
from django.utils import timezone
from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse

from ochered_app import models


def qr_page(request):
    try:
        return render(request, "qr.html", context={})
    except Exception as e:
        return HttpResponse(str(e))


@login_required
def statistic_show(request):
    if not request.user.is_staff:
        return redirect("queue")
    return render(request, "statistic_chart.html", context={})


def show_queue(request):
    in_progress_tickets = models.Ticket.objects.filter(status="in_progress")
    waiting_tickets = models.Ticket.objects.filter(status="waiting")

    context = {
        "in_progress_tickets": in_progress_tickets,
        "waiting_tickets": waiting_tickets,
    }
    return render(request, "queue_list.html", context)


def register_ticket(request):
    new_ticket = models.Ticket.objects.create()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "queue_updates", {"type": "new_ticket", "ticket_number": new_ticket.number}
    )
    return redirect("ticket", ticket_uuid=new_ticket.uuid)


def ticket_view(request, ticket_uuid):
    try:
        ticket = models.Ticket.objects.get(uuid=ticket_uuid)
    except models.Ticket.DoesNotExist:
        return render(
            request,
            "ticket.html",
            {"ticket": None, "is_from_subnet": request.is_from_subnet},
        )

    return render(
        request,
        "ticket.html",
        {"ticket": ticket, "is_from_subnet": request.is_from_subnet},
    )


@login_required
def queue(request):
    consultant = models.Consultant.objects.get(user=request.user)
    tickets = models.Ticket.objects.filter(status="waiting").order_by("number")
    current_ticket = models.Ticket.objects.filter(
        status="in_progress", consultant=consultant
    ).first()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        tickets_data = list(tickets.values("number"))
        current_ticket_data = current_ticket.number if current_ticket else None
        return JsonResponse(
            {"tickets": tickets_data, "current_ticket": current_ticket_data}
        )
    total_waiter = models.Ticket.objects.filter(status="waiting").count()
    return render(
        request,
        "queue.html",
        {
            "consultant": consultant,
            "tickets": tickets,
            "current_ticket": current_ticket,
            "total_waiter": total_waiter,
        },
    )


@login_required
def call_next(request):
    consultant = models.Consultant.objects.get(user=request.user)
    current_ticket = models.Ticket.objects.filter(
        status="in_progress", consultant=consultant
    ).first()

    if not current_ticket:
        next_ticket = (
            models.Ticket.objects.filter(status="waiting").order_by("number").first()
        )
        if next_ticket:
            next_ticket.status = "in_progress"
            next_ticket.consultant = consultant
            next_ticket.save()

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"queue_{consultant.id}",
                {
                    "type": "update_queue",
                    "ticket_number": next_ticket.number,
                    "action": "call_next",
                },
            )

            return JsonResponse({"ticket_number": next_ticket.number})
    return JsonResponse(
        {"error": "No waiting tickets or you already have a ticket in progress"},
        status=400,
    )


@login_required
def complete_ticket(request):
    consultant = models.Consultant.objects.get(user=request.user)
    current_ticket = models.Ticket.objects.filter(
        status="in_progress", consultant=consultant
    ).first()
    if current_ticket:
        current_ticket.status = "served"
        current_ticket.save()

        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"queue_{consultant.id}",
            {
                "type": "update_queue",
                "ticket_number": current_ticket.number,
                "action": "complete_ticket",
            },
        )

        return JsonResponse({"success": "Ticket marked as served"})
    return JsonResponse({"error": "No ticket in progress"}, status=400)


def logout_view(request):
    logout(request)
    return redirect("login")


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("queue")
    return render(request, "login.html", context={})


def get_consultant_statistics():
    today = timezone.localtime(timezone.now())

    start_of_day = datetime.datetime(
        today.year, today.month, today.day, tzinfo=today.tzinfo
    )
    end_of_day = (
        start_of_day + datetime.timedelta(days=1) - datetime.timedelta(microseconds=1)
    )

    start_of_week = start_of_day - datetime.timedelta(days=today.weekday())
    end_of_week = (
        start_of_week + datetime.timedelta(days=7) - datetime.timedelta(microseconds=1)
    )

    start_of_month = datetime.datetime(today.year, today.month, 1, tzinfo=today.tzinfo)
    if today.month == 12:
        start_of_next_month = datetime.datetime(
            today.year + 1, 1, 1, tzinfo=today.tzinfo
        )
    else:
        start_of_next_month = datetime.datetime(
            today.year, today.month + 1, 1, tzinfo=today.tzinfo
        )
    end_of_month = start_of_next_month - datetime.timedelta(microseconds=1)

    tickets = (
        models.Ticket.objects.filter(status=models.Ticket.STATUS_SERVED)
        .exclude(consultant__user__username="evgen")
        .annotate(
            service_time=ExpressionWrapper(
                F("served_at") - F("in_progress_at"), output_field=DurationField()
            )
        )
    )


    statistics = (
        tickets.values("consultant__user__first_name", "consultant__user__last_name")
        .annotate(
            avg_service_time=Avg("service_time"),
            tickets_served_today=Count(
                "number",
                filter=Q(served_at__gte=start_of_day, served_at__lte=end_of_day),
            ),
            tickets_served_week=Count(
                "number",
                filter=Q(served_at__gte=start_of_week, served_at__lte=end_of_week),
            ),
            tickets_served_month=Count(
                "number",
                filter=Q(served_at__gte=start_of_month, served_at__lte=end_of_month),
            ),
        )
        .order_by("consultant__user__last_name", "consultant__user__first_name")
    )

    statistics_list = list(statistics)
    for stat in statistics_list:
        avg_service_time = stat["avg_service_time"]
        if avg_service_time is not None:
            stat["avg_service_time"] = avg_service_time.total_seconds()
        else:
            stat["avg_service_time"] = 0


    return statistics_list


class ConsultantStatisticsView(View):
    def get(self, request):
        data = get_consultant_statistics()
        return JsonResponse(data, safe=False)

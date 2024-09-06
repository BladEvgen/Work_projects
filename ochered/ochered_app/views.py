import datetime

from django.contrib import messages
from asgiref.sync import async_to_sync
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from channels.layers import get_channel_layer
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.db.models import (
    F,
    Q,
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
)
from django.views import View
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from ochered_app import models, utils
import logging

logger = logging.getLogger(__name__)


def qr_page(request):
    try:
        # utils.generate_qr_code()
        return render(request, "qrpage.html", context={})
    except Exception as e:
        logger.error(f"Qr_page view: {e}")
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
    try:
        consultant = models.Consultant.objects.get(user=request.user)
        logger.info(f"Consultant {consultant} accessed the queue.")

        tickets = models.Ticket.objects.filter(status="waiting").order_by("number")
        current_ticket = models.Ticket.objects.filter(
            status="in_progress", consultant=consultant
        ).first()

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            tickets_data = list(tickets.values("number"))
            current_ticket_data = (
                {
                    "number": current_ticket.number,
                    "start_time": current_ticket.in_progress_at.timestamp(),
                }
                if current_ticket
                else None
            )
            logger.info(f"AJAX request processed for consultant {consultant}.")
            return JsonResponse(
                {"tickets": tickets_data, "current_ticket": current_ticket_data}
            )

        total_waiter = models.Ticket.objects.filter(status="waiting").count()
        logger.info(
            f"Consultant {consultant} viewed queue with {total_waiter} waiting tickets."
        )
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
    except Exception as e:
        logger.error(f"An error occurred in the queue view: {e}")
        return JsonResponse(
            {"error": "An error occurred while processing the request."}, status=500
        )


@login_required
def call_next(request):
    try:
        consultant = models.Consultant.objects.get(user=request.user)
        logger.info(f"Consultant {consultant} is calling the next ticket.")

        current_ticket = models.Ticket.objects.filter(
            status="in_progress", consultant=consultant
        ).first()

        if not current_ticket:
            next_ticket = (
                models.Ticket.objects.filter(status="waiting")
                .order_by("number")
                .first()
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

                logger.info(
                    f"Consultant {consultant} called ticket {next_ticket.number}."
                )
                return JsonResponse({"ticket_number": next_ticket.number})
            else:
                logger.warning(
                    f"No waiting tickets available for consultant {consultant}."
                )
        else:
            logger.warning(f"Consultant {consultant} already has a ticket in progress.")
        return JsonResponse(
            {"error": "No waiting tickets or you already have a ticket in progress"},
            status=400,
        )
    except Exception as e:
        logger.error(f"An error occurred in the call_next view: {e}")
        return JsonResponse(
            {"error": "An error occurred while processing the request."}, status=500
        )


@login_required
def complete_ticket(request):
    try:
        consultant = models.Consultant.objects.get(user=request.user)
        logger.info(f"Consultant {consultant} is attempting to complete a ticket.")

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

            logger.info(
                f"Ticket {current_ticket.number} marked as served by consultant {consultant}."
            )
            return JsonResponse({"success": "Ticket marked as served"})
        else:
            logger.warning(f"No ticket in progress for consultant {consultant}.")
        return JsonResponse({"error": "No ticket in progress"}, status=400)
    except Exception as e:
        logger.error(f"An error occurred in the complete_ticket view: {e}")
        return JsonResponse(
            {"error": "An error occurred while processing the request."}, status=500
        )


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


@login_required
def change_data(request, username):
    if request.user.username != username:
        return redirect("change_data", username=request.user.username)
    user_profile = get_object_or_404(models.Consultant, user=request.user)

    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if password and confirm_password:
            if password != confirm_password:
                messages.error(request, "Passwords do not match.")
            elif not utils.password_check(password):
                messages.error(request, "Password does not meet the required criteria.")
            else:
                request.user.set_password(password)

        if first_name:
            request.user.first_name = first_name
        if last_name:
            request.user.last_name = last_name

        request.user.save()
        user_profile.save()
        messages.success(request, "Profile updated successfully.")

        return redirect(reverse("profile", args=[username]))

    return render(request, "change_data.html", context={"user_profile": user_profile})


class ProfileView(View):
    template_name = "profile.html"

    def get(self, request, username):
        if request.user.username != username:
            return redirect("profile", username=request.user.username)
        user = get_object_or_404(User, username=username)
        user_profile, created = models.Consultant.objects.get_or_create(user=user)
        tickets = models.Ticket.objects.filter(consultant=user_profile).order_by(
            "-created_at"
        )[:1]
        served_ticket_count = models.Ticket.objects.filter(
            consultant=user_profile, status="served"
        ).count()
        return render(
            request,
            template_name=self.template_name,
            context={
                "user_profile": user_profile,
                "tickets": tickets,
                "served_ticket_count": served_ticket_count,
            },
        )

    def post(self, request, username):
        if request.user.username != username:
            return redirect("profile", username=request.user.username)
        user = get_object_or_404(User, username=username)
        user_profile, created = models.Consultant.objects.get_or_create(user=user)
        return render(
            request,
            template_name=self.template_name,
            context={"user_profile": user_profile},
        )


@login_required
def load_more_tickets(request, username):
    if request.user.username != username:
        return redirect("profile", username=request.user.username)
    user = get_object_or_404(User, username=username)
    user_profile = get_object_or_404(models.Consultant, user=user)
    page = request.GET.get("page", 1)
    tickets = models.Ticket.objects.filter(consultant=user_profile).order_by(
        "-created_at"
    )
    paginator = Paginator(tickets, 10)
    page_obj = paginator.get_page(page)
    tickets_data = [
        {
            "number": ticket.number,
            "status": ticket.get_status_display(),
            "created_at": localtime(ticket.created_at).strftime("%H:%M %d.%m.%Y"),
        }
        for ticket in page_obj
    ]
    return JsonResponse({"tickets": tickets_data, "has_more": page_obj.has_next()})

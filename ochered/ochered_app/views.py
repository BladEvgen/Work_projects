from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import redirect, render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout

from ochered_app import models, utils


def qr_page(request):
    try:
        utils.generate_qr_code()
        return render(request, "qr.html", context={})
    except Exception as e:
        return HttpResponse(str(e))


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
        return render(request, "ticket.html", {"ticket": None, "is_from_subnet": request.is_from_subnet})

    return render(request, "ticket.html", {"ticket": ticket, "is_from_subnet": request.is_from_subnet})


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

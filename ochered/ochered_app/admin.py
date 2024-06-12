from django.contrib import admin
from django.db.models import Count, Q
from ochered_app.models import Ticket, Consultant

admin.site.site_header = "Панель управления"
admin.site.index_title = "Администрирование сайта"
admin.site.site_title = "Администрирование"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("get_user_username", "get_table_number", "status", "created_at")
    search_fields = ("consultant__user__username", "consultant__table_number", "status")
    ordering = ("-created_at", "status")
    list_editable = ("status",)
    list_display_links = None

    def get_user_username(self, obj):
        return obj.consultant.user.username if obj.consultant else None

    get_user_username.short_description = "Username"

    def get_table_number(self, obj):
        return obj.consultant.table_number if obj.consultant else None

    get_table_number.short_description = "Table Number"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(status="in_progress")


@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("user", "table_number", "tickets_served_count")
    search_fields = ("user__username", "table_number")
    ordering = ("table_number", "user__username")
    change_list_template = "admin/consultant_changelist.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.annotate(
            tickets_served=Count("ticket", filter=Q(ticket__status="served"))
        )
        return qs

    def tickets_served_count(self, obj):
        return obj.tickets_served

    tickets_served_count.short_description = "Tickets Served"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        total_waiting = Ticket.objects.filter(status="waiting").count()
        extra_context["total_waiting"] = total_waiting
        return super().changelist_view(request, extra_context=extra_context)

from datetime import datetime
from ochered_app import models

from django.contrib import admin
from django.db.models import Count, Q

admin.site.site_header = "Панель управления"
admin.site.index_title = "Администрирование сайта"
admin.site.site_title = "Администрирование"


def humanize_time(seconds):
    intervals = (
        ("год", "года", "лет", 31536000),
        ("месяц", "месяца", "месяцев", 2592000),
        ("неделя", "недели", "недель", 604800),
        ("день", "дня", "дней", 86400),
        ("час", "часа", "часов", 3600),
        ("минута", "минуты", "минут", 60),
        ("секунда", "секунды", "секунд", 1),
    )
    result = []

    for one, few, many, count in intervals:
        value = seconds // count
        if value:
            seconds -= value * count
            if value % 10 == 1 and value % 100 != 11:
                name = one
            elif 2 <= value % 10 <= 4 and (value % 100 < 10 or value % 100 >= 20):
                name = few
            else:
                name = many
            result.append(f"{value} {name}")

    return ", ".join(result)


@admin.register(models.Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "get_number",
        "get_user_username",
        "get_table_number",
        "get_status_display",
        "get_created_at",
        "time_spent",
    )
    search_fields = ("consultant__user__username", "consultant__table_number", "status")
    date_hierarchy = "created_at"
    ordering = ("-created_at", "status")
    list_filter = ("consultant",)

    def get_user_username(self, obj):
        return obj.consultant.user.username if obj.consultant else None

    get_user_username.short_description = "Имя пользователя"

    def get_table_number(self, obj):
        return obj.consultant.table_number if obj.consultant else None

    get_table_number.short_description = "Номер столика"

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.exclude(status="test")

    def time_spent(self, obj):
        if obj.in_progress_at and obj.served_at:
            seconds = (obj.served_at - obj.in_progress_at).total_seconds()
            return humanize_time(int(seconds))
        return None

    time_spent.short_description = "Время обслуживания"

    def get_status_display(self, obj):
        return obj.get_status_display()

    get_status_display.short_description = "Статус обслуживания"

    def get_created_at(self, obj):
        return obj.created_at

    get_created_at.short_description = "Дата создания"

    def get_number(self, obj):
        return obj.number

    get_number.short_description = "Номер талона"


@admin.register(models.Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "table_number",
        "tickets_served_count",
        "tickets_served_today",
        "tickets_served_this_month",
        "tickets_served_this_year",
    )
    search_fields = ("user__username", "table_number")
    ordering = ("table_number", "user__username")
    change_list_template = "admin/consultant_changelist.html"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        today = datetime.today()
        start_of_today = datetime(today.year, today.month, today.day)
        start_of_month = datetime(today.year, today.month, 1)
        start_of_year = datetime(today.year, 1, 1)

        qs = qs.annotate(
            tickets_served=Count("ticket", filter=Q(ticket__status="served")),
            tickets_served_today=Count(
                "ticket",
                filter=Q(
                    ticket__status="served", ticket__served_at__gte=start_of_today
                ),
            ),
            tickets_served_this_month=Count(
                "ticket",
                filter=Q(
                    ticket__status="served", ticket__served_at__gte=start_of_month
                ),
            ),
            tickets_served_this_year=Count(
                "ticket",
                filter=Q(ticket__status="served", ticket__served_at__gte=start_of_year),
            ),
        )
        return qs

    def tickets_served_count(self, obj):
        return obj.tickets_served

    tickets_served_count.short_description = "Обслуженные талоны"

    def tickets_served_today(self, obj):
        return obj.tickets_served_today

    tickets_served_today.short_description = "Обслуженные талоны сегодня"

    def tickets_served_this_month(self, obj):
        return obj.tickets_served_this_month

    tickets_served_this_month.short_description = "Обслуженные талоны в этом месяце"

    def tickets_served_this_year(self, obj):
        return obj.tickets_served_this_year

    tickets_served_this_year.short_description = "Обслуженные талоны в этом году"

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        total_waiting = models.Ticket.objects.filter(status="waiting").count()
        extra_context["total_waiting"] = total_waiting
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(models.AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ("ip", "device", "os", "browser", "route", "access_time")
    search_fields = ("ip", "device", "os", "browser", "route")
    ordering = ("-access_time",)
    list_filter = ("device", "os", "browser")
    date_hierarchy = "access_time"
    actions = ["delete_all_logs"]

    def delete_all_logs(self, request, queryset):
        models.AccessLog.objects.all().delete()
        self.message_user(request, "Все логи были успешно удалены.")

    delete_all_logs.short_description = "Удалить все логи"

    def has_delete_permission(self, request, obj=None):
        return obj is None or super().has_delete_permission(request, obj)

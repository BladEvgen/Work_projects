from django.contrib import admin
from ochered_app.models import Ticket, Consultant

admin.site.site_header = "Панель управления"
admin.site.index_title = "Администрирование сайта"
admin.site.site_title = "Администрирование"


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("get_user_username", "get_table_number", "status", "created_at")
    search_fields = ("consultant__user__username", "consultant__table_number", "status")
    ordering = ("consultant__table_number", "consultant__user__username")
    list_editable = ("status",)

    def get_user_username(self, obj):
        return obj.consultant.user.username if obj.consultant else None

    get_user_username.short_description = "Username"

    def get_table_number(self, obj):
        return obj.consultant.table_number if obj.consultant else None

    get_table_number.short_description = "Table Number"


@admin.register(Consultant)
class ConsultantAdmin(admin.ModelAdmin):
    list_display = ("user", "table_number")
    search_fields = ("user__username", "table_number")
    ordering = ("table_number", "user__username")

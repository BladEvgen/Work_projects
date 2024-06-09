from django.urls import path
from ochered_app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("qr/", views.qr_page, name="qr_page"),
    path("queue/", views.queue, name="queue"),
    path("accounts/login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register_ticket/", views.register_ticket, name="register_ticket"),
    path("call_next/", views.call_next, name="call_next"),
    path("complete_ticket/", views.complete_ticket, name="complete_ticket"),
    path("show_queue/", views.show_queue, name="show_queue"),
    path("ticket/<uuid:ticket_uuid>/", views.ticket_view, name="ticket"),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

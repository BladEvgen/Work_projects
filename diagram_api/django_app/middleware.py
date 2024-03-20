from django.utils import timezone
from django_app import models
import httpagentparser


class LogAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            return self.get_response(request)

        response = self.get_response(request)

        ip_address = request.META.get("REMOTE_ADDR")
        if not ip_address:
            ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "")

        user_agent = request.META.get("HTTP_USER_AGENT", "")
        parsed_agent = httpagentparser.detect(user_agent)

        device = parsed_agent.get("platform", "Unknown")

        os = parsed_agent.get("os", {}).get("name", "Unknown")

        browser = parsed_agent.get("browser", {}).get("name", "Unknown")

        route = request.path

        access_time = timezone.now()

        models.AccessLog.objects.create(
            ip=ip_address,
            device=device,
            os=os,
            browser=browser,
            route=route,
            access_time=access_time,
        )

        return response

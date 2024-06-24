from django.utils import timezone
from ochered_app import models
import httpagentparser


class LogAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ignored_ips = ["192.168.12.27", "192.168.13.89"]

        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = ip_address.split(",")[0].strip() if ip_address else None

        if ip_address in ignored_ips:
            return self.get_response(request)

        if request.path.startswith("/admin/"):
            return self.get_response(request)

        response = self.get_response(request)

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

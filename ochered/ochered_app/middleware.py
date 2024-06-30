import ipaddress
import httpagentparser
from ochered_app import models
from django.utils import timezone

class LogAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.ignored_ips = ["192.168.12.27", "192.168.13.89", "127.0.0.1", "91.231.66.227"]
        self.subnet = ipaddress.ip_network("172.16.16.0/20")

    def __call__(self, request):
        ip_address = request.META.get("HTTP_X_FORWARDED_FOR", "")
        ip_address = ip_address.split(",")[0].strip() if ip_address else request.META.get("REMOTE_ADDR")

        if not ip_address or ip_address in ["127.0.0.1", "::1"]:
            ip_address = "127.0.0.1"

        request.is_from_subnet = ip_address in self.ignored_ips or (ip_address and ipaddress.ip_address(ip_address) in self.subnet)

        response = self.get_response(request)

        user_agent = request.META.get("HTTP_USER_AGENT", "")
        parsed_agent = httpagentparser.detect(user_agent)

        device = parsed_agent.get("platform", {}).get("name", "Unknown")
        device_version = parsed_agent.get("platform", {}).get("version", "Unknown")
        os = parsed_agent.get("os", {}).get("name", "Unknown")
        browser = parsed_agent.get("browser", {}).get("name", "Unknown")
        browser_version = parsed_agent.get("browser", {}).get("version", "Unknown")
        route = request.path
        access_time = timezone.now()

        models.AccessLog.objects.create(
            ip=ip_address,
            device=f"{device} {device_version}",
            os=f"{os}",
            browser=f"{browser} {browser_version}",
            route=route,
            access_time=access_time,
        )

        return response

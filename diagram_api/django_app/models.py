from django.db import models


class Debtors(models.Model):
    name = models.CharField(max_length=255)
    count = models.IntegerField()

    def __str__(self) -> str:
        return self.name


class AccessLog(models.Model):
    ip = models.CharField(max_length=100)
    device = models.CharField(max_length=100)
    os = models.CharField(max_length=100)
    browser = models.CharField(max_length=100)
    route = models.CharField(max_length=200)
    access_time = models.DateTimeField()

    def __str__(self):
        return f"IP: {self.ip}, Device: {self.device}, OS: {self.os}, Browser: {self.browser}, Route: {self.route}, Access Time: {self.access_time}"

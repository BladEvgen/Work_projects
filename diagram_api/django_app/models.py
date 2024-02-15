from django.db import models


# Create your models here.
class Debtors(models.Model):
    name = models.CharField(max_length=255)
    count = models.IntegerField()

    def __str__(self) -> str:
        return self.name

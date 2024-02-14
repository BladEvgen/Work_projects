from django.urls import path
from . import views

urlpatterns = [
    path("diagram/", views.specialty_api, name="speciality_api"),
    path("", views.home, name="home"),
]

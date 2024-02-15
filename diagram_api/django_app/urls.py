from django.urls import path
from . import views

urlpatterns = [
    path("diagram/", views.specialty_api, name="speciality_api"),
    path("load_data/", views.load_data, name="load_data"),
    path("", views.home, name="home"),
]

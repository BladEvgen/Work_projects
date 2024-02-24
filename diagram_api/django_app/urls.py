from django.urls import path
from . import views

urlpatterns = [
    path("diagram/", views.specialty_api, name="speciality_api"),
    path("get_marks/", views.get_marks_for_tutor, name="get_marks"),
    path("load_data/", views.load_data, name="load_data"),
    path("charts", views.charts, name="charts"),
    path("", views.home, name="home"),
]

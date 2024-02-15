import datetime

from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import models, utils
from .config import execute_query, get_database_connection

STUDENTS = {
    "students": "isStudent = 1",
    "om": "isStudent = 1 AND professionNameRU IN ('Общая медицина', 'Медицина')",
    "stom": "isStudent = 1 AND professionNameRU = 'Стоматология'",
    "farm": "isStudent = 1 AND professionNameRU = 'Фармация'",
    "small_faculty": "isStudent = 1 AND professionNameRU IN ('Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
    "rez_mag_doc": "isStudent = 1 AND professionNameRU NOT IN ('Общая медицина', 'Медицина', 'Стоматология', 'Фармация', 'Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
}

TUTORS = {"tutor": "isStudent = 0"}

# Cache for storing data
cache = {"last_updated": None, "data": None}


def home(request):
    return JsonResponse(data={"message": "Home OK"})


@api_view(["GET"])
def specialty_api(request):
    global cache
    response_data = {"diagram_1": {}, "diagram_3": {}, "diagram_4": {}}
    try:
        start_time = datetime.datetime.now()
        if (
            cache["last_updated"] is None
            or (datetime.datetime.now() - cache["last_updated"]).seconds > 10
        ):
            print(
                "No cache available or cache expired. Fetching data from the database..."
            )
            with get_database_connection() as conn:
                for key, value in STUDENTS.items():
                    count = execute_query(
                        conn, f"SELECT COUNT(StudentID) FROM users WHERE {value}"
                    )
                    response_data["diagram_1"][key] = count

                for k, v in TUTORS.items():
                    count = execute_query(
                        conn, f"SELECT COUNT(TutorID) FROM users WHERE {v}"
                    )
                    response_data["diagram_3"][k] = count

            debtors = models.Debtors.objects.all()

            for d in debtors:
                response_data["diagram_4"][d.name] = d.count
            cache["data"] = response_data
            cache["last_updated"] = datetime.datetime.now()

        else:
            print("Using cached data...")
            response_data = cache["data"]

        end_time = datetime.datetime.now()
        time_taken = end_time - start_time
        print(f"Page loaded in {time_taken.total_seconds()} seconds.")
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    return Response(response_data)


def load_data(request):
    if request.method == "POST":
        excel_file = request.FILES["file"]
        data = utils.count_debtors(excel_file)

        models.Debtors.objects.all().delete()

        for key, value in data.items():
            debtor = models.Debtors(name=key, count=value)
            debtor.save()

    return render(request, "load_data.html", {})

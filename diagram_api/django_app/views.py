import datetime
from django.http import JsonResponse
from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from contextlib import closing
from rest_framework import status
from . import models, utils
from .config import execute_query, platonus_connection, journal_connection
from django.core.cache import cache as django_cache
from django.views.decorators.csrf import csrf_exempt

STUDENTS = {
    "students": "isStudent = 1",
    "om": "isStudent = 1 AND professionNameRU IN ('Общая медицина', 'Медицина')",
    "stom": "isStudent = 1 AND professionNameRU = 'Стоматология'",
    "farm": "isStudent = 1 AND professionNameRU = 'Фармация'",
    "small_faculty": "isStudent = 1 AND professionNameRU IN ('Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
    "rez_mag_doc": "isStudent = 1 AND professionNameRU NOT IN ('Общая медицина', 'Медицина', 'Стоматология', 'Фармация', 'Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
}


TUTORS = {"tutor": "isStudent = 0"}

cache = {"last_updated": None, "data": None}


def home(request):
    return JsonResponse(data={"message": "Home OK"})


def charts(request):
    return render(request, "chart.html", {})


@api_view(["GET"])
def specialty_api(request) -> Response:
    global cache
    response_data = {"diagram_1": {}, "diagram_4": {}}

    try:
        start_time = datetime.datetime.now()
        if (
            cache["last_updated"] is None
            or (datetime.datetime.now() - cache["last_updated"]).seconds > 10
        ):
            print(
                "No cache available or cache expired. Fetching data from the database..."
            )
            with platonus_connection() as conn:
                for key, value in STUDENTS.items():
                    count = execute_query(
                        conn, f"SELECT COUNT(StudentID) FROM users WHERE {value}"
                    )
                    response_data["diagram_1"][key] = count

            debtors = models.Debtors.objects.all()

            for d in debtors:
                response_data["diagram_4"][d.name] = d.count
            cache["data"] = response_data
            cache["last_updated"] = datetime.datetime.now()

        else:
            response_data = cache["data"]

        end_time = datetime.datetime.now()
        time_taken = end_time - start_time
        print(f"Page loaded in {time_taken.total_seconds()} seconds.")
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    return Response(response_data)


def load_data(request):
    context = {}
    try:
        if request.method == "POST":
            excel_file = request.FILES["file"]
            data = utils.count_debtors(excel_file)

            models.Debtors.objects.all().delete()

            for key, value in data.items():
                debtor = models.Debtors(name=key, count=value)
                debtor.save()

    except Exception as e:
        context["error"] = str(e)

    return render(request, "load_data.html", context)


@api_view(["GET"])
@csrf_exempt
def get_marks_for_tutor(request):
    try:
        iin = request.GET.get("iin")
        date_range = request.GET.get("date_range", "7")
        date_filter = datetime.datetime.now() - datetime.timedelta(days=int(date_range))

        date_filter_str = date_filter.strftime("%Y-%m-%d %H:%M:%S")

        cached_data = django_cache.get(f"{iin}_{date_range}")
        if cached_data is not None:
            return Response(cached_data)

        with closing(platonus_connection()) as platonus_conn, closing(
            journal_connection()
        ) as journal_conn:
            if iin:
                tutor_query = f"SELECT tutorID, lastname, firstname FROM users WHERE IIN = '{iin}'"
            else:
                tutor_query = "SELECT DISTINCT tutorID, lastname, firstname FROM users"
            tutor_ids = execute_query(platonus_conn, tutor_query, many=True)

            tutor_diagram = {}
            no_scores = []
            for tutor_id, lastname, firstname in tutor_ids:
                if tutor_id is not None:
                    marks_query = f"SELECT Mark FROM marks_from_journal WHERE tutorID = '{tutor_id}' AND Date >= '{date_filter_str}'"
                    marks = execute_query(journal_conn, marks_query, many=True)

                    if marks:
                        tutor_diagram[tutor_id] = {
                            "fullName": f"{lastname}_{firstname}",
                            "marks": [mark[0] for mark in marks],
                        }
                    else:
                        no_scores.append(tutor_id)

        response = {"tutor_diagram": tutor_diagram}
        if no_scores:
            response["no_scores"] = no_scores

        django_cache.set(f"{iin}_{date_range}", response, 30)

        return Response(response)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

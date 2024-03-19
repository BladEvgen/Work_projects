import datetime
from contextlib import closing

from django.core.cache import cache as django_cache
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import models, utils
from .config import execute_query, journal_connection, platonus_connection

STUDENTS = {
    "students": "isStudent = 1",
    "om": "isStudent = 1 AND professionNameRU IN ('Общая медицина', 'Медицина')",
    "stom": "isStudent = 1 AND professionNameRU = 'Стоматология'",
    "farm": "isStudent = 1 AND professionNameRU = 'Фармация'",
    "small_faculty": "isStudent = 1 AND professionNameRU IN ('Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
    "rez_mag_doc": "isStudent = 1 AND professionNameRU NOT IN ('Общая медицина', 'Медицина', 'Стоматология', 'Фармация', 'Сестринское дело', 'Медико-профилактическое дело', 'Общественная здравоохранение (2)')",
}


def home(request):
    return JsonResponse(data={"message": "Home OK"})


def charts(request):
    return render(request, "chart.html", {})


def tutor_charts(request):
    return render(request, "tutor_charts.html", {})


@api_view(["GET"])
def specialty_api(request) -> Response:
    try:
        response_data = django_cache.get("response_data")

        if response_data is None:
            response_data: dict[str, dict] = {
                "diagram_1": {},
                "diagram_2": {},
                "diagram_4": {},
            }

            language_mapping: dict[int, str] = {
                1: "Rus",
                2: "Kaz",
                3: "Eng",
                51: "Multi",
            }

            with platonus_connection() as conn:
                for key, value in STUDENTS.items():
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(StudentID) FROM users WHERE {value}")
                    count = cursor.fetchone()[0]
                    response_data["diagram_1"][key] = count

                cursor.execute(
                    "SELECT StudyLanguageID, COUNT(*) FROM users WHERE StudyLanguageID != 0 AND isStudent = 1 GROUP BY StudyLanguageID"
                )
                study_language_counts = cursor.fetchall()
                for id, count in study_language_counts:
                    language = language_mapping.get(int(id), "Unknown")
                    response_data["diagram_2"][language] = count

            debtors = models.Debtors.objects.all()

            for d in debtors:
                response_data["diagram_4"][d.name] = d.count

            django_cache.set("response_data", response_data, 10)

        return Response(response_data)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

            context["success"] = "Файл успешно загружен!"

    except Exception as e:
        context["error"] = str(e)

    return render(request, "load_data.html", context)


def comments(request) -> HttpResponse:
    with_comments = request.GET.get("with_comments", False)
    context = {}
    try:
        with_comments = str(with_comments).lower() == "true"

        if with_comments:
            comments = utils.get_comments_from_db(
                comments_enabled=True, ignore_vdovtsev=True
            )
        else:
            comments = utils.get_comments_from_db(
                comments_enabled=False, ignore_vdovtsev=True
            )

        # Предположим, что `comments` - это строка или объект bytes, содержащий HTML-данные
        response = HttpResponse(comments, content_type="text/html")
        response["Content-Disposition"] = 'attachment; filename="get_comments.html"'
        return response

    except Exception as e:
        context["error"] = str(e)
        return HttpResponse(status=500, content=str(e))


@api_view(["GET"])
@csrf_exempt
def get_marks_for_tutor(request):
    try:
        iin = request.query_params.get("iin", None)
        date_range = request.query_params.get("date_range", "7")
        date_filter = datetime.datetime.now() - datetime.timedelta(days=int(date_range))

        date_filter_str = date_filter.strftime("%Y-%m-%d %H:%M:%S")

        cached_data = django_cache.get(f"{iin}_{date_range}")
        if cached_data is not None:
            return Response(cached_data)

        with closing(platonus_connection()) as platonus_conn, closing(
            journal_connection()
        ) as journal_conn:
            tutor_query = "SELECT DISTINCT tutorID, lastname, firstname FROM users"
            if iin:
                tutor_query += f" WHERE IIN = '{iin}'"
            tutor_ids = execute_query(platonus_conn, tutor_query, many=True)

            tutor_diagram = {}
            tutor_count_with_marks = 0
            tutor_count_without_marks = 0
            for tutor_id, lastname, firstname in tutor_ids:
                if tutor_id is not None:
                    marks_query = f"SELECT Mark FROM marks_from_journal WHERE tutorID = '{tutor_id}' AND Date >= '{date_filter_str}'"
                    marks = execute_query(journal_conn, marks_query, many=True)

                    if marks:
                        tutor_diagram[tutor_id] = {
                            "fullName": f"{lastname}_{firstname}",
                            "marks": sorted([mark[0] for mark in marks], reverse=True),
                        }
                        tutor_count_with_marks += 1
                    else:
                        if iin:
                            tutor_diagram[tutor_id] = {
                                "fullName": f"{lastname}_{firstname}",
                                "marks": None,
                            }
                        tutor_count_without_marks += 1

        response = {
            "tutor_diagram": tutor_diagram,
            "tutor_count_with_marks": tutor_count_with_marks,
            "tutor_count_without_marks": tutor_count_without_marks,
        }

        django_cache.set(f"{iin}_{date_range}", response, 300)

        return Response(response)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

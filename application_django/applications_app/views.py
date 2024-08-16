import os
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

import pdfkit
import requests
from django.conf import settings
from django.db import transaction
from rest_framework import status
from django.template import engines
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from applications_app import models, permissions

# Настройка логгера
log_filename = os.path.join(
    settings.BASE_DIR, "logs", f'logs_{datetime.now().strftime("%Y%m%d_%H")}.log'
)
os.makedirs(os.path.dirname(log_filename), exist_ok=True)

log_level = logging.DEBUG if settings.DEBUG else logging.WARNING
logging.basicConfig(
    level=log_level,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler() if settings.DEBUG else logging.NullHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Константы
CATEGORY_STUDY_YEARS = {
    "rezident": {
        "professions": {
            "Урология взрослая, детская": 3.7,
            "Неотложная медицина": 3.7,
        }
    },
    "om": {"professions": {"Общая медицина": 5}},
    "dentistry": {"professions": {"Стоматология": 6}},
    "sd": {"professions": {"Сестринское Дело": 3.5}},
}


# Вспомогательные функции
def get_study_years(profession_name: str) -> float:
    """
    Получить продолжительность обучения в годах для данной профессии.

    Args:
        profession_name (str): Название профессии.

    Returns:
        float: Количество лет, требуемое для обучения. По умолчанию 5 лет, если профессия не найдена.

    Логгирование:
        Логгирует предупреждение, если профессия не найдена в определенных категориях.
    """
    for category, data in CATEGORY_STUDY_YEARS.items():
        if profession_name in data["professions"]:
            return data["professions"][profession_name]
    logger.warning(f"Профессия {profession_name} не найдена, используется значение по умолчанию 5 лет.")
    return 5


def calculate_finish_month_day(enroll_order_date: datetime, study_years: float) -> str:
    """
    Рассчитать месяц и день окончания обучения на основе даты зачисления и продолжительности обучения.

    Args:
        enroll_order_date (datetime): Дата зачисления студента.
        study_years (float): Количество лет, требуемое для обучения.

    Returns:
        str: Рассчитанная дата окончания в формате "дд.мм", если количество лет не является целым числом.
        Если количество лет обучения целое, возвращает значение по умолчанию "15.07".

    Логгирование:
        Логгирует ошибку при расчете и возвращает значение по умолчанию "15.07".
    """
    try:

        if study_years.is_integer():
            return "15.07"

        full_years = int(study_years)
        months_offset = int((study_years - full_years) * 12)
        planned_graduation_date = (
            enroll_order_date
            + timedelta(days=365 * full_years)
            + timedelta(days=30 * months_offset)
        )
        return planned_graduation_date.strftime("%d.%m")
    except Exception as e:
        logger.error(f"Ошибка в calculate_finish_month_day: {e}")
        return "15.07"



def fetch_student_data(student_id: int, is_student: bool) -> dict:
    """
    Получить данные студента из внешнего API.

    Args:
        student_id (int): ID студента.
        is_student (bool): Указывает, является ли человек студентом.

    Returns:
        dict: Данные студента, полученные из API, или None, если произошла ошибка.

    Логгирование:
        Логгирует любые ошибки, возникшие при запросе к API или его обработке.
    """
    try:
        headers = {"Access-Token": settings.SECRET_API}
        params = {"id": student_id, "isStudent": str(is_student).lower()}
        response = requests.get(
            f"{settings.API_URL}/reference", headers=headers, params=params
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Исключение RequestException при получении данных студента: {e}")
        return None
    except Exception as e:
        logger.error(f"Неожиданная ошибка в fetch_student_data: {e}")
        return None


def enrich_student_data(data: dict) -> dict:
    """
    Обогащает данные студента, добавляя рассчитанные поля, такие как год начала обучения,
    планируемый год выпуска, дату окончания и другие данные.

    Args:
        data (dict): Исходные данные студента.

    Returns:
        dict: Обогащенные данные студента с добавленными расчетными полями.
    """
    try:
        birth_date = datetime.strptime(data["BirthDate"], "%Y-%m-%d")
        enroll_order_date = datetime.strptime(data["enroll_order_date"], "%Y-%m-%d")
        current_year = enroll_order_date.year

        # Определение возраста студента на момент зачисления
        age_at_enroll = current_year - birth_date.year
        if (enroll_order_date.month < birth_date.month) or (
            enroll_order_date.month == birth_date.month
            and enroll_order_date.day < birth_date.day
        ):
            age_at_enroll -= 1

        # Логика определения года начала обучения
        if (
            enroll_order_date.year == 2020
            and enroll_order_date.month == 11
            and age_at_enroll > 17
        ):
            # Если студент старше 17 или 18 лет и зачислен в ноябре 2020 года, 
            # предположим, что он начал обучение раньше.
            start_year = birth_date.year + 17
        else:
            start_year = enroll_order_date.year

        # Проверка на студентов, зачисленных позже (например, в 2023 году)
        if start_year < enroll_order_date.year:
            start_year = enroll_order_date.year

        profession_name = data.get("professionNameRU", "")
        study_years = get_study_years(profession_name)
        planned_graduation_year = start_year + int(study_years)
        finish_month_day = calculate_finish_month_day(enroll_order_date, study_years)

        return {
            **data,
            "start_year": start_year,
            "planned_graduation_year": planned_graduation_year,
            "current_study_year_start": start_year,
            "current_study_year_finish": start_year + 1,
            "finish_month_day": finish_month_day,
        }
    except Exception as e:
        logger.error(f"Ошибка в enrich_student_data: {e}")
        return None





def render_html(document: models.Document) -> str:
    """
    Сгенерировать HTML контент для документа, используя его шаблон и связанные данные студента.

    Args:
        document (models.Document): Объект документа, для которого необходимо сгенерировать HTML.

    Returns:
        str: Путь к сгенерированному HTML файлу или None, если произошла ошибка.

    Логгирование:
        Логгирует любые ошибки, возникшие в процессе генерации HTML.
    """
    try:
        template = get_object_or_404(models.DocumentTemplate, slug=document.type)

        student_data = document.full_student_data
        if not student_data:
            logger.error("Данные студента отсутствуют в документе.")
            raise ValueError("Данные студента отсутствуют")

        approvals = document.approvals.select_related(
            "approved_by__profile", "approved_by__role"
        ).all()

        context = {
            "student_fullname": f"{student_data.get('lastname', '')} {student_data.get('firstname', '')} {student_data.get('patronymic', '')}",
            "student_course": student_data.get("CourseNumber", ""),
            "student_data": {
                "NameRu": student_data.get("NameRu", ""),
                "code": student_data.get("code", ""),
                "specializations": student_data.get("specializations", ""),
                "current_study_year_start": student_data.get(
                    "current_study_year_start"
                ),
                "current_study_year_finish": student_data.get(
                    "current_study_year_finish"
                ),
                "start_year": student_data.get("start_year"),
                "planned_graduation_year": student_data.get("planned_graduation_year"),
                "finish_month_day": student_data.get("finish_month_day"),
            },
            "document": document,
            "approvals": approvals,
        }

        django_engine = engines["django"]

        # Корректируем: Открываем файл без параметра encoding
        with template.file.open("rb") as template_file:
            template_content = template_file.read().decode("utf-8")

        template_obj = django_engine.from_string(template_content)
        html_content = template_obj.render(context)

        file_path = save_html_file(html_content, document.id, document.type)
        return file_path
    except Exception as e:
        logger.error(f"Ошибка в render_html: {e}")
        return None


def save_html_file(html_content: str, document_id: int, doc_type: str) -> str:
    """
    Сохранить сгенерированный HTML контент в файл.

    Args:
        html_content (str): HTML контент, который необходимо сохранить.
        document_id (int): ID документа.
        doc_type (str): Тип документа.

    Returns:
        str: Путь к сохраненному HTML файлу или None, если произошла ошибка.

    Логгирование:
        Логгирует любые ошибки, возникшие при сохранении файла.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_filename = f"{document_id}_{doc_type}_{timestamp}.html"
        file_path = os.path.join(
            settings.MEDIA_ROOT, "generated_documents", unique_filename
        )
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return file_path
    except Exception as e:
        logger.error(f"Ошибка в save_html_file: {e}")
        return None


def generate_pdf(html_file_path: str, document_id: int) -> str:
    """
    Сгенерировать PDF из HTML файла.

    Args:
        html_file_path (str): Путь к HTML файлу.
        document_id (int): ID документа.

    Returns:
        str: Путь к сгенерированному PDF файлу или None, если произошла ошибка.

    Логгирование:
        Логгирует любые ошибки, возникшие в процессе генерации PDF.
    """
    try:
        if not html_file_path or not os.path.exists(html_file_path):
            logger.error(
                f"Неверный путь к HTML файлу или файл не существует: {html_file_path}"
            )
            return None

        pdf_filename = f"{document_id}_signed.pdf"
        pdf_path = os.path.join(
            settings.MEDIA_ROOT, "generated_documents", pdf_filename
        )
        options = {
            "page-size": "A4",
            "encoding": "UTF-8",
            "enable-local-file-access": None,
        }

        pdfkit.from_file(html_file_path, pdf_path, options=options)
        if not os.path.exists(pdf_path):
            logger.error(f"Не удалось сгенерировать PDF для {pdf_path}.")
            return None

        return pdf_path
    except Exception as e:
        logger.error(f"Ошибка в generate_pdf: {e}")
        return None


def generate_document_files(document: models.Document, generate_pdf_now: bool) -> None:
    """
    Сгенерировать файлы документа, включая HTML и PDF (при необходимости).

    Args:
        document (models.Document): Объект документа, для которого необходимо сгенерировать файлы.
        generate_pdf_now (bool): Указывает, следует ли сразу генерировать PDF.

    Логгирование:
        Логгирует любые ошибки, возникшие в процессе генерации файлов.
    """
    try:
        html_file_path = render_html(document)
        if not html_file_path:
            logger.error(
                f"Не удалось сгенерировать HTML для документа {document.id}. Генерация PDF пропущена."
            )
            return

        document.content["generated_file"] = html_file_path

        if generate_pdf_now:
            pdf_file_path = generate_pdf(html_file_path, document.id)
            if not pdf_file_path:
                logger.error(f"Не удалось сгенерировать PDF для документа {document.id}.")
                return

            document.content["pdf_file"] = pdf_file_path

        document.save()
    except Exception as e:
        logger.error(f"Ошибка в generate_document_files: {e}")
        raise


def should_generate_pdf_now(document: models.Document) -> bool:
    """
    Определяет, следует ли немедленно генерировать PDF для данного документа.

    Args:
        document (models.Document): Объект документа.

    Returns:
        bool: True, если PDF должен быть сгенерирован немедленно, иначе False.
    """
    return document.auto_mode or document.check_approvals()


# Классы API View
class CreateDocumentView(APIView):
    """
    API View для создания документа. Обрабатывает запрос на создание нового документа,
    генерирует HTML и (при необходимости) PDF файлы.

    Методы:
        post(request): Обрабатывает POST-запрос на создание документа.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """
        Обрабатывает POST-запрос на создание документа.

        Args:
            request: Запрос, содержащий параметры создания документа.

        Returns:
            Response: HTTP-ответ с результатом создания документа.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе создания документа.
        """
        try:
            student_id = request.GET.get("id")
            if not student_id:
                return Response(
                    {"error": "Необходимо указать ID студента"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            is_student = request.GET.get("isStudent", "True").lower() == "true"
            doc_type = request.GET.get("type")
            if not doc_type:
                return Response(
                    {"error": "Необходимо указать тип документа"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            auto_mode = request.GET.get("auto_mode", "true").lower() == "true"
            student_data = fetch_student_data(student_id, is_student)
            if not student_data:
                return Response(
                    {"error": "Не удалось получить данные студента"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            enriched_data = enrich_student_data(student_data)
            if not enriched_data:
                return Response(
                    {"error": "Не удалось обработать данные студента"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            document_template = get_object_or_404(
                models.DocumentTemplate, slug=doc_type
            )
            document = models.Document.objects.create(
                type=doc_type,
                title=document_template.name,
                full_student_data=enriched_data,
                student_id=student_id,
                status=(
                    "approved_for_editing" if not auto_mode else "approved_for_signing"
                ),
                auto_mode=auto_mode,
            )

            with ThreadPoolExecutor(max_workers=1 if settings.DEBUG else 4) as executor:
                executor.submit(
                    generate_document_files, document, should_generate_pdf_now(document)
                )

            return Response(
                {"message": "Документ успешно создан"},
                status=status.HTTP_201_CREATED,
            )
        except Exception as e:
            logger.error(f"Ошибка в CreateDocumentView: {e}")
            return Response(
                {"error": "Не удалось создать документ"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EditDocumentView(APIView):
    """
    API View для редактирования документа. Обрабатывает запросы на просмотр и редактирование документа.

    Методы:
        get(request, document_id): Возвращает путь к сгенерированному HTML-файлу для редактирования.
        post(request, document_id): Обновляет содержимое документа и генерирует новые файлы.
    """
    permission_classes = [IsAuthenticated, permissions.CanEditDocument]

    def get(self, request, document_id):
        """
        Обрабатывает GET-запрос для получения HTML-файла документа для редактирования.

        Args:
            request: Запрос на получение данных.
            document_id (int): ID документа.

        Returns:
            Response: HTTP-ответ с путем к сгенерированному HTML-файлу или ошибкой.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе получения данных документа.
        """
        try:
            document = get_object_or_404(models.Document, pk=document_id)
            if document.status not in ["approved_for_editing", "approved_for_signing"]:
                return Response(
                    {"error": "Документ не готов для редактирования"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {"html_file_path": document.content.get("generated_file")},
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Ошибка в EditDocumentView (GET): {e}")
            return Response(
                {"error": "Не удалось получить данные документа"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, document_id):
        """
        Обрабатывает POST-запрос для обновления содержимого документа и генерации новых файлов.

        Args:
            request: Запрос на обновление данных документа.
            document_id (int): ID документа.

        Returns:
            Response: HTTP-ответ с результатом обновления документа или ошибкой.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе редактирования документа.
        """
        try:
            document = get_object_or_404(models.Document, pk=document_id)
            if document.status != "approved_for_editing":
                return Response(
                    {"error": "Документ не готов для редактирования"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if request.data:
                document.update_content(request.data)
                document.status = "approved_for_signing"

            with ThreadPoolExecutor(max_workers=1 if settings.DEBUG else 4) as executor:
                executor.submit(
                    generate_document_files, document, should_generate_pdf_now(document)
                )

            return Response(
                {
                    "html_file_path": document.content.get("generated_file"),
                    "pdf_path": document.content.get("pdf_file"),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            logger.error(f"Ошибка в EditDocumentView (POST): {e}")
            return Response(
                {"error": "Не удалось отредактировать документ"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ApproveDocumentView(APIView):
    """
    API View для одобрения или отклонения документа. Обрабатывает запросы на одобрение или отклонение документа.

    Методы:
        post(request, document_id): Обрабатывает POST-запрос на одобрение или отклонение документа.
    """
    permission_classes = [IsAuthenticated, permissions.CanApproveDocument]

    @transaction.atomic
    def post(self, request, document_id):
        """
        Обрабатывает POST-запрос для одобрения или отклонения документа.

        Args:
            request: Запрос на одобрение или отклонение документа.
            document_id (int): ID документа.

        Returns:
            Response: HTTP-ответ с результатом одобрения или отклонения документа или ошибкой.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе одобрения документа.
        """
        try:
            document = get_object_or_404(models.Document, pk=document_id)
            role = request.user.role.role
            approve = request.data.get("approve", True)

            if approve:
                document.approve_section(role.name, request.user)
            else:
                document.reject_section(role.name, request.user)

            if should_generate_pdf_now(document):
                with ThreadPoolExecutor(
                    max_workers=1 if settings.DEBUG else 4
                ) as executor:
                    executor.submit(generate_document_files, document, True)

            return Response({"status": document.status}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Ошибка в ApproveDocumentView: {e}")
            return Response(
                {"error": "Не удалось одобрить документ"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class SignDocumentView(APIView):
    """
    API View для подписания документа. Обрабатывает запросы на получение PDF и подписания документа.

    Методы:
        get(request, document_id): Возвращает путь к сгенерированному PDF-файлу для подписания.
        post(request, document_id): Подписывает документ с использованием переданного ключа и пароля.
    """
    permission_classes = [IsAuthenticated, permissions.CanSignDocument]

    def get(self, request, document_id):
        """
        Обрабатывает GET-запрос для получения пути к PDF-файлу для подписания.

        Args:
            request: Запрос на получение данных.
            document_id (int): ID документа.

        Returns:
            Response: HTTP-ответ с путем к PDF-файлу или ошибкой.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе получения PDF-файла.
        """
        try:
            document = get_object_or_404(models.Document, pk=document_id)
            if document.status != "approved_for_signing":
                return Response(
                    {"error": "Документ не готов для подписания"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pdf_path = document.content.get("pdf_file")
            if not pdf_path:
                return Response(
                    {"error": "PDF недоступен"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({"pdf_path": pdf_path}, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Ошибка в SignDocumentView (GET): {e}")
            return Response(
                {"error": "Не удалось получить документ"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, document_id):
        """
        Обрабатывает POST-запрос для подписания документа.

        Args:
            request: Запрос на подписание документа.
            document_id (int): ID документа.

        Returns:
            Response: HTTP-ответ с результатом подписания документа или ошибкой.

        Логгирование:
            Логгирует любые ошибки, возникшие в процессе подписания документа.
        """
        try:
            document = get_object_or_404(models.Document, pk=document_id)
            if document.status != "approved_for_signing":
                return Response(
                    {"error": "Документ не готов для подписания"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            pdf_path = document.content.get("pdf_file")
            if not pdf_path:
                return Response(
                    {"error": "PDF недоступен"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            key_file = request.FILES.get("keyPath")
            if not key_file:
                return Response(
                    {"error": "Требуется файл ключа"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            password = request.data.get("password")
            if not password:
                return Response(
                    {"error": "Требуется пароль"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            with open(pdf_path, "rb") as pdf_file:
                files = {
                    "file": (f"{document_id}_sign.pdf", pdf_file, "application/pdf"),
                    "keyPath": key_file,
                }
                data = {"password": password}
                response = requests.post(
                    "https://ecp.medkrmu.kz/sign", files=files, data=data
                )

            if response.status_code == 200:
                signed_pdf = response.content
                document.status = "signed"
                document.save()
                return Response({"signed_pdf": signed_pdf}, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"error": "Ошибка при подписании документа"}, status=response.status_code
                )
        except Exception as e:
            logger.error(f"Ошибка в SignDocumentView (POST): {e}")
            return Response(
                {"error": "Не удалось подписать документ"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

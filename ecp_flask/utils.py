import os
import io
import base64
import logging
import datetime
import requests
import mysql.connector
from uuid import uuid4
from typing import Union
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table

import logger

logger = logging.getLogger(__name__)



dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    

HOST_URL = "https://ecp.medkrmu.kz/"

db_connection_certificate = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_CERTIFICATES"),
)

db_connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_ECP"),
)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def get_packages() -> list:
    query = (
        "SELECT package_name FROM packages WHERE signed_status = 1 ORDER BY date DESC"
    )
    result = execute_query(query, db=db_connection_certificate)
    return [row[0] for row in result] if result else []


def save_to_database(
    original_file_name: str, signed_file_path: str, step: str, status_message: str
) -> int:
    sql = "INSERT INTO signed_files (original_file_name, signed_file_path, step, status_message) VALUES (%s, %s, %s, %s)"
    val = (original_file_name, signed_file_path, step, status_message)
    execute_query(sql, val, db=db_connection)

    result = execute_query("SELECT LAST_INSERT_ID()", db=db_connection)
    return result[0][0] if result else None


def execute_query(
    query: str, params: tuple = None, db: mysql.connector.connect = None
) -> list:
    cursor = db.cursor()
    try:
        cursor.execute(query, params)
        result = cursor.fetchall()
        db.commit()
        return result
    except mysql.connector.Error as err:
        logger.error(f"Error: {err}")
        db.rollback()
        return []
    finally:
        cursor.close()


def initialize_database():
    create_table_query = """
        CREATE TABLE IF NOT EXISTS signed_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            original_file_name VARCHAR(255),
            signed_file_path VARCHAR(255),
            sign_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            step VARCHAR(255),
            status_message VARCHAR(255)
        )
    """
    execute_query(create_table_query, db=db_connection)


def update_signed_status(filenames):
    if not filenames:
        logger.warning("No filenames provided for status update.")
        return

    placeholders = ', '.join(['%s'] * len(filenames))
    update_query = f"UPDATE certificate SET signed_status = 2 WHERE filename IN ({placeholders})"

    try:
        with db_connection_certificate.cursor() as cursor:
            cursor.execute(update_query, filenames)
            db_connection_certificate.commit()
            logger.info(f"Updated signed_status to 2 for filenames: {filenames}")
    except mysql.connector.Error as err:
        logger.error(f"Database error during status update: {err}")
        db_connection_certificate.rollback()
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")


def print_verification_info(verification_result: dict) -> dict:
    status = verification_result.get("status", 0)
    signers = verification_result.get("signers", [])

    if status == 200:
        for signer in signers:
            for certificate in signer.get("certificates", []):
                organization = certificate["subject"].get("organization", "")
                common_name = certificate["subject"].get("commonName", "")
                public_key = certificate.get("publicKey", "")

                if "ORGANIZATION" not in certificate.get("keyUser", []):
                    logger.error(
                        "Invalid ECP key: Missing required organization permission."
                    )
                    return None

                if organization:
                    gen_time_str = signer["tsp"]["genTime"]
                    if gen_time_str:
                        gen_time = datetime.datetime.strptime(
                            gen_time_str, "%Y-%m-%dT%H:%M:%S.%f%z"
                        )
                        formatted_gen_time = (
                            gen_time + datetime.timedelta(hours=5)
                        ).strftime("%d.%m.%Y %H:%M")
                        return {
                            "organization": organization,
                            "common_name": common_name,
                            "public_key": public_key,
                            "formatted_gen_time": formatted_gen_time,
                        }
                else:
                    logger.error(
                        "Error: Missing organization information in the certificate."
                    )
                    return None
    else:
        logger.error("Verification status is not successful.")
        return None


def get_verification_result(file_id: int) -> dict:
    url = f"{HOST_URL}/verify?id={file_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"Verification fails: {str(e)}")
        return {"status": "error", "message": str(e)}


def sign_file_gos(key: str, password: str, file: Union[str, bytes]) -> tuple:
    decoded_file_path = None
    try:
        base64_key_string = get_base_64_key_string(key)
        
        if isinstance(file, bytes):
            encoded_file = base64.b64encode(file).decode("utf-8")
            original_file_name = "processed_pdf.pdf"
        elif isinstance(file, str):
            with open(file, "rb") as f:
                file_data = f.read()
            encoded_file = base64.b64encode(file_data).decode("utf-8")
            original_file_name = os.path.basename(file)
        else:
            raise ValueError("file parameter must be a filename (str) or bytes data")
        
        data = {
            "data": encoded_file,
            "signers": [
                {"key": base64_key_string, "password": password, "keyAlias": None}
            ],
            "withTsp": True,
            "tsaPolicy": "TSA_GOST_POLICY",
            "detached": False,
        }
        
        response = requests.post("http://localhost:14579/cms/sign", json=data)
        response.raise_for_status()
        response_data = response.json()

        if "cms" not in response_data:
            logger.error(f"Error in signing service: {response_data}")
            raise KeyError("cms key not found in response")

        decoded_data = base64.b64decode(response_data["cms"])
        unique_id = str(uuid4())
        unique_filename = f"decoded_file_{unique_id[:10]}.cms"

        decoded_file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        with open(decoded_file_path, "wb") as f:
            f.write(decoded_data)

        file_id = save_to_database(
            original_file_name,
            decoded_file_path,
            "sign_file_gos",
            "OK, PDF table",
        )

        return decoded_data, file_id
    except Exception as e:
        logger.exception(f"Error signing file {file}: {str(e)}")
        if decoded_file_path:
            save_to_database(
                original_file_name,
                decoded_file_path,
                "sign_file_gos",
                str(e),
            )
        raise


def get_base_64_key_string(key: str) -> str:
    with open(key, "rb") as file:
        key_contents = file.read()
    return base64.b64encode(key_contents).decode("utf-8")


def process_pdf(original_pdf: bytes, verification_info: dict) -> bytes:
    output_pdf = io.BytesIO()
    font_name = "Montserrat-Regular"
    font_path = "/var/www/ecp.medkrmu/KRMU-main/font/Montserrat-Regular.ttf"
    pdfmetrics.registerFont(TTFont(font_name, font_path, "UTF-8"))

    styles = getSampleStyleSheet()
    for style_name in ["Title", "BodyText", "Normal", "Heading1"]:
        styles[style_name].fontName = font_name
        styles[style_name].fontSize = 10

    styleN = styles["Normal"]
    styleH = styles["Heading1"]
    current_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M")
    table_data = [
        [
            Paragraph("Ключ", styleH),
            Paragraph(
                verification_info["public_key"][0:7]
                + "..."
                + verification_info["public_key"][-9:],
                styleN,
            ),
        ],
        [
            Paragraph("Организация", styleH),
            Paragraph(verification_info.get("organization", "N/A"), styleN),
        ],
        [
            Paragraph("Подписал", styleH),
            Paragraph(verification_info.get("common_name", "N/A"), styleN),
        ],
        [
            Paragraph("Время подписания", styleH),
            Paragraph(
                verification_info.get("formatted_gen_time", current_time), styleN
            ),
        ],
    ]

    table_style = [
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
        ("LEADING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("COLWIDTHS", (0, 0), (0, 1), 200),
        ("COLWIDTHS", (1, 0), (-1, -1), 300),
        ("SPLITTABLE", (0, 0), (-1, -1), 1),
    ]

    table = Table(table_data, style=table_style, splitByRow=True, hAlign="CENTER")
    doc = SimpleDocTemplate(output_pdf, pagesize=A4)
    flowables = [Paragraph("Данные о подписи", styles["Title"]), table]

    try:
        doc.build(flowables)
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")

    output_pdf.seek(0)
    return output_pdf.read()


def merge_pdfs(original_pdf_path: str, new_page_pdf: bytes) -> bytes:
    output = io.BytesIO()
    original_pdf = PdfReader(original_pdf_path)
    new_page = PdfReader(io.BytesIO(new_page_pdf))

    pdf_writer = PdfWriter()
    for page in original_pdf.pages:
        pdf_writer.add_page(page)

    pdf_writer.add_page(new_page.pages[0])
    pdf_writer.write(output)
    output.seek(0)
    return output.read()


def rename_pdfs_to_old(directory):
    for filename in os.listdir(directory):
        if filename.endswith(".pdf"):
            old_filename = os.path.join(directory, filename)
            new_filename = os.path.join(directory, f"{filename}.old")
            os.rename(old_filename, new_filename)

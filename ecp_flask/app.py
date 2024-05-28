import io
import os
import json
import base64
import datetime
from uuid import uuid4

import requests
import mysql.connector
from flask_cors import CORS
from dotenv import load_dotenv
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table
from flask import Flask, jsonify, make_response, render_template, request

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)

db_connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_ECP"),
)

db_cursor = db_connection.cursor()

db_cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS signed_files (
        id INT AUTO_INCREMENT PRIMARY KEY,
        original_file_name VARCHAR(255),
        signed_file_path VARCHAR(255),
        sign_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )
"""
)

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
signed_folder = os.path.join(app.root_path, "signed")
if not os.path.exists(signed_folder):
    os.makedirs(signed_folder)


def save_to_database(original_file_name, signed_file_path):
    sql = "INSERT INTO signed_files (original_file_name, signed_file_path) VALUES (%s, %s)"
    val = (original_file_name, signed_file_path)
    db_cursor.execute(sql, val)
    db_connection.commit()

    db_cursor.execute("SELECT LAST_INSERT_ID()")
    file_id = db_cursor.fetchone()[0]

    return file_id


@app.route("/test")
def test():
    return render_template("example.html")


def process_pdf(original_pdf, verification_info):
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

    flowables = [
        Paragraph("Данные о подписи", styles["Title"]),
        table,
    ]

    try:
        doc.build(flowables)
    except Exception as e:
        print(f"Error generating with: {e}")

    output_pdf.seek(0)
    return output_pdf.read()


def merge_pdfs(original_pdf_path, new_page_pdf):
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


@app.route("/sign", methods=["POST"])
def sign_file():
    key_files = request.files.getlist("keyPath")
    files = request.files.getlist("file")
    password = request.form["password"]

    key_path = ""
    file_path = ""
    file_id = None

    for file in key_files:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        key_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    for file in files:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
        original_filename = os.path.splitext(file.filename)[0]

    signed_pdf, file_id = sign_file_gos(key_path, password, file_path)

    verification_info = print_verification_info(get_verification_result(file_id))

    if verification_info is not None:
        try:
            merged_pdf_content = process_pdf(signed_pdf, verification_info)

            merged_pdf = merge_pdfs(file_path, merged_pdf_content)

            final_signed_pdf, final_file_id = sign_file_gos(
                key_path, password, merged_pdf
            )

            signed_filename = f"{original_filename}_signed.pdf"
            signed_file_path = os.path.join(signed_folder, signed_filename)

            with open(signed_file_path, "wb") as f:
                f.write(final_signed_pdf)

            save_to_database(os.path.basename(file_path), signed_file_path)

            response = make_response(final_signed_pdf)
            response.headers["Content-Disposition"] = (
                f'attachment; filename="{original_filename}_merged_signed.pdf"'
            )
            response.headers["Content-Type"] = "application/pdf"
            if os.path.exists(key_path):
                os.remove(key_path)
            if os.path.exists(file_path):
                os.remove(file_path)
            return response
        except Exception as e:
            return jsonify({"message": f"Error: {e}"}), 400
    else:
        return jsonify({"message": "Incorrect SingKey Data"}), 400


def print_verification_info(verification_result):
    status = verification_result.get("status", 0)
    signers = verification_result.get("signers", [])

    if status == 200:
        for signer in signers:
            for certificate in signer.get("certificates", []):
                organization = certificate["subject"].get("organization", "")
                common_name = certificate["subject"].get("commonName", "")
                public_key = certificate.get("publicKey", "")

                if "ORGANIZATION" not in certificate.get("keyUser", []):
                    print(
                        "Не правильный ЭЦП ключ: Отсутствует необходимое разрешение на организацию."
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
                        print(f"Организация: {organization}")
                        print(f"Подписано: {common_name}")
                        print(f"Публичный ключ: {public_key[:7]}....{public_key[-9:]}")
                        print(f"Время подписи: {formatted_gen_time}")
                        return {
                            "organization": organization,
                            "common_name": common_name,
                            "public_key": public_key,
                            "formatted_gen_time": formatted_gen_time,
                        }
                else:
                    print(
                        "Ошибка: Отсутствует информация об организации в сертификате."
                    )
                    return None
    else:
        print("Статус верификации не является успешным.")
        return None


def get_verification_result(file_id):
    url = f"http://localhost:5000/verify?id={file_id}"
    response = requests.get(url)
    verification_result = response.json()
    return verification_result


def sign_file_gos(key, password, file):
    base64_key_string = get_base_64_key_string(key)
    encoded_file = base64.b64encode(
        file if isinstance(file, bytes) else open(file, "rb").read()
    ).decode("utf-8")

    data = {
        "data": encoded_file,
        "signers": [{"key": base64_key_string, "password": password, "keyAlias": None}],
        "withTsp": True,
        "tsaPolicy": "TSA_GOST_POLICY",
        "detached": False,
    }
    data_json_sign = json.dumps(data)
    headers = {"Content-Type": "application/json"}
    url = "http://localhost:14579/cms/sign"
    response = requests.post(url, data=data_json_sign, headers=headers)
    response_data = response.json()

    if "cms" not in response_data:
        print(f"Error in signing service: {response_data}")
        raise KeyError("cms key not found in response")

    encoded_data = response_data["cms"]
    decoded_data = base64.b64decode(encoded_data)

    unique_id = str(uuid4())
    unique_filename = "decoded_file_" + str(unique_id[:10]) + ".cms"
    decoded_file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

    with open(decoded_file_path, "wb") as f:
        f.write(decoded_data)

    file_id = save_to_database(
        os.path.basename(file) if isinstance(file, str) else "processed_pdf.pdf",
        decoded_file_path,
    )

    return decoded_data, file_id


def get_base_64_key_string(key) -> str:
    with open(key, "rb") as file:
        key_contents = file.read()
    encoded_key = base64.b64encode(key_contents)
    base64_key_string = encoded_key.decode("utf-8")
    return base64_key_string


@app.route("/verify", methods=["GET"])
def verify_data():
    file_id = request.args.get("id")
    if not file_id:
        return "File ID is required", 400

    db_cursor.execute(
        "SELECT signed_file_path FROM signed_files WHERE id = %s", (file_id,)
    )
    result = db_cursor.fetchone()
    if not result:
        return "File not found", 404

    file_path = result[0]

    with open(file_path, "rb") as f:
        data_to_verify = base64.b64encode(f.read()).decode("utf-8")

    url = "http://localhost:14579/cms/verify"
    headers = {"Content-Type": "application/json"}
    payload = {"revocationCheck": ["OCSP"], "cms": data_to_verify}
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    response_data = response.json()
    return jsonify(response_data)


if __name__ == "__main__":
    app.run(debug=True)

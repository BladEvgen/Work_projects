import io
import os
import base64
import datetime
import pandas as pd
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
from flask import Flask, jsonify, make_response, render_template, request, send_file

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)
HOST_URL = "https://ecp.medkrmu.kz/"

db_connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_ECP"),
)
db_connection_certificate = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_CERTIFICATES"),
)

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
signed_folder = os.path.join(app.root_path, "signed")
os.makedirs(signed_folder, exist_ok=True)


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
        print(f"Error: {err}")
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


initialize_database()


def change_permissions_and_ownership(
    directory: str, uid: int = 1001, gid: int = 1001, permissions: int = 0o666
):
    for root, dirs, files in os.walk(directory):
        for momo in dirs + files:
            path = os.path.join(root, momo)
            os.chmod(path, permissions)
            os.chown(path, uid, gid)
        os.chmod(root, permissions)
        os.chown(root, uid, gid)


def save_to_database(
    original_file_name: str, signed_file_path: str, step: str, status_message: str
) -> int:
    sql = "INSERT INTO signed_files (original_file_name, signed_file_path, step, status_message) VALUES (%s, %s, %s, %s)"
    val = (original_file_name, signed_file_path, step, status_message)
    execute_query(sql, val, db=db_connection)

    result = execute_query("SELECT LAST_INSERT_ID()", db=db_connection)
    return result[0][0] if result else None


def get_packages() -> list:
    query = (
        "SELECT package_name FROM packages WHERE signed_status = 1 ORDER BY date DESC"
    )
    result = execute_query(query, db=db_connection_certificate)
    return [row[0] for row in result] if result else []


@app.route("/ecp_sign", methods=["GET", "POST"])
def ecp_sign_view():
    if request.method == "GET":
        packages = get_packages()
        return render_template("ecp_sign.html", packages=packages)


@app.route("/download_excel", methods=["POST"])
def download_excel():
    data = request.json
    package_name = data.get("package")

    if not package_name:
        return jsonify({"error": "Package name is required"}), 400

    query = "SELECT * FROM certificate WHERE package_name = %s"
    results = execute_query(query, (package_name,), db=db_connection_certificate)
    if not results:
        return jsonify({"error": "No data found for the selected package"}), 404

    df = pd.DataFrame(results)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sheet1")

    output.seek(0)
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        download_name=f"{package_name}.xlsx",
        as_attachment=True,
    )


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
        print(f"Error generating with: {e}")

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
            os.rename(
                os.path.join(directory, filename),
                os.path.join(directory, f"{filename}.old"),
            )


@app.route("/sign", methods=["POST"])
def sign_file():
    key_files = request.files.getlist("keyPath")
    files = request.files.getlist("file")
    password = request.form["password"]
    package = request.form.get("package")

    key_path = ""
    file_path = ""
    signed_file_path = ""
    file_id = None
    successfully_signed_files = []

    for file in key_files:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        key_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

    try:
        if package:
            directory = (
                f"/var/www/kirill/certificates.medkrmu/cert_date_base/{package}/pdf/"
            )
            signed_folder = directory
            os.makedirs(directory, exist_ok=True)
        else:
            directory = "/var/www/kirill/certificates.medkrmu/cert_date_base/ecp_signed_files_folder/pdf/"
            signed_folder = directory
            os.makedirs(directory, exist_ok=True)

        verification_info = None
        if package:
            for filename in os.listdir(directory):
                if filename.endswith(".pdf"):
                    file_path = os.path.join(directory, filename)
                    signed_pdf, file_id = sign_file_gos(key_path, password, file_path)
                    verification_info = print_verification_info(
                        get_verification_result(file_id)
                    )
                    break

        if not verification_info:
            return (
                jsonify({"message": "Verification info could not be retrieved."}),
                400,
            )

        files_to_sign = []
        if package:
            for filename in os.listdir(directory):
                if filename.endswith(".pdf"):
                    file_path = os.path.join(directory, filename)
                    original_filename = os.path.splitext(filename)[0]

                    signed_pdf, file_id = sign_file_gos(key_path, password, file_path)

                    merged_pdf_content = process_pdf(signed_pdf, verification_info)
                    merged_pdf = merge_pdfs(file_path, merged_pdf_content)
                    final_signed_pdf, final_file_id = sign_file_gos(
                        key_path, password, merged_pdf
                    )

                    signed_filename = f"{original_filename}.pdf"
                    files_to_sign.append((signed_filename, final_signed_pdf))
                    successfully_signed_files.append(original_filename)
        else:
            for file in files:
                file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
                original_filename = os.path.splitext(file.filename)[0]

                signed_pdf, file_id = sign_file_gos(key_path, password, file_path)

                merged_pdf_content = process_pdf(signed_pdf, verification_info)
                merged_pdf = merge_pdfs(file_path, merged_pdf_content)
                final_signed_pdf, final_file_id = sign_file_gos(
                    key_path, password, merged_pdf
                )

                signed_filename = f"{original_filename}.pdf"
                files_to_sign.append((signed_filename, final_signed_pdf))

        rename_pdfs_to_old(directory)

        for signed_filename, final_signed_pdf in files_to_sign:
            signed_file_path = os.path.join(signed_folder, signed_filename)
            with open(signed_file_path, "wb") as f:
                f.write(final_signed_pdf)

            save_to_database(
                os.path.basename(signed_file_path),
                signed_file_path,
                "sign_file",
                "OK",
            )

        if os.path.exists(key_path):
            os.remove(key_path)

        if package and successfully_signed_files:
            try:
                with db_connection_certificate.cursor() as cursor:
                    placeholders = ",".join(["%s"] * len(successfully_signed_files))
                    update_query = f"UPDATE certificate SET signed_status = 2 WHERE id IN ({placeholders})"
                    update_package = (
                        "UPDATE packages SET signed_status = 2 WHERE package_name = %s"
                    )
                    cursor.execute(update_query, tuple(successfully_signed_files))
                    cursor.execute(update_package, (package,))
                    db_connection_certificate.commit()
            except Exception as e:
                print(f"Error: {e}")

        return jsonify({"message": "All files signed successfully"}), 200

    except Exception as e:
        save_to_database(
            os.path.basename(file_path), signed_file_path, "sign_file", str(e)
        )
        return jsonify({"message": f"Error: {e}"}), 400


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


def get_verification_result(file_id: int) -> dict:
    url = f"{HOST_URL}/verify?id={file_id}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error making request to {url}: {e}")
        return {"status": "error", "message": str(e)}


def sign_file_gos(key: str, password: str, file: str) -> tuple:
    try:
        base64_key_string = get_base_64_key_string(key)
        encoded_file = base64.b64encode(
            file if isinstance(file, bytes) else open(file, "rb").read()
        ).decode("utf-8")

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
        response_data = response.json()

        if "cms" not in response_data:
            print(f"Error in signing service: {response_data}")
            raise KeyError("cms key not found in response")

        decoded_data = base64.b64decode(response_data["cms"])
        unique_id = str(uuid4())
        unique_filename = f"decoded_file_{unique_id[:10]}.cms"
        decoded_file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

        with open(decoded_file_path, "wb") as f:
            f.write(decoded_data)

        file_id = save_to_database(
            os.path.basename(file) if isinstance(file, str) else "processed_pdf.pdf",
            decoded_file_path,
            "sign_file_gos",
            "OK, PDF table",
        )

        return decoded_data, file_id
    except Exception as e:
        save_to_database(
            os.path.basename(file) if isinstance(file, str) else "processed_pdf.pdf",
            decoded_file_path,
            "sign_file_gos",
            str(e),
        )
        return None, None


def get_base_64_key_string(key: str) -> str:
    with open(key, "rb") as file:
        key_contents = file.read()
    return base64.b64encode(key_contents).decode("utf-8")


@app.route("/verify", methods=["GET"])
def verify_data():
    file_id = request.args.get("id")
    if not file_id:
        return "File ID is required", 400

    result = execute_query(
        "SELECT signed_file_path FROM signed_files WHERE id = %s",
        (file_id,),
        db=db_connection,
    )
    if not result:
        return "File not found", 404

    file_path = result[0][0]
    with open(file_path, "rb") as f:
        data_to_verify = base64.b64encode(f.read()).decode("utf-8")

    url = "http://localhost:14579/cms/verify"
    response = requests.post(
        url, json={"revocationCheck": ["OCSP"], "cms": data_to_verify}
    )
    return jsonify(response.json())


if __name__ == "__main__":
    app.run(host="0.0.0.0")

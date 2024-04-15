import base64
import datetime
import json
import os
from uuid import uuid4

import mysql.connector
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request, render_template
from flask_cors import CORS
from PyPDF2 import PdfWriter


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


def add_into_pdf(filename, info_to_add: dict):

    writer = PdfWriter()
    writer.add_blank_page(210, 297)
    with open(filename, "wb") as file:
        writer.write(file)


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

    returnfile, file_id = sign_file_gos(key_path, password, file_path)

    verification_info = print_verification_info(get_verification_result(file_id))

    if verification_info is not None:
        add_into_pdf(filename=file_path, info_to_add=verification_info)

        response = make_response(returnfile)

        response.headers["Content-Disposition"] = 'attachment; filename="test.pdf"'
        return response
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
    with open(file, "rb") as files:
        file_contents = files.read()
    encoded_key = base64.b64encode(file_contents)
    file_contents = encoded_key.decode("utf-8")

    data = {
        "data": file_contents,
        "signers": [{"key": base64_key_string, "password": password, "keyAlias": None}],
        "withTsp": True,
        "tsaPolicy": "TSA_GOST_POLICY",
        "detached": False,
    }
    data_json_sign = json.dumps(data)
    headers = {"Content-Type": "application/json"}
    url = "http://localhost:14579/cms/sign"
    response = requests.post(url, data=data_json_sign, headers=headers)
    response_data = json.loads(response.text)

    encoded_data = response_data["cms"]

    decoded_data = base64.b64decode(encoded_data)

    unique_id = str(uuid4())
    unique_filename = "decoded_file_" + str(unique_id[:10]) + ".cms"
    decoded_file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_filename)

    with open(decoded_file_path, "wb") as f:
        f.write(decoded_data)

    file_id: int | None | json.Any = save_to_database(
        os.path.basename(file), decoded_file_path
    )

    if os.path.exists(key):
        os.remove(key)
    #! REMOVING FILE
    if os.path.exists(file):
        os.remove(file)

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

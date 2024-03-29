import os
import json
import base64
import requests
import datetime
import mysql.connector
from flask import Flask, request, make_response, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from uuid import uuid4

dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

app = Flask(__name__)
CORS(app)

db_connection = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
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

# Установка папки для загрузок
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")


def save_to_database(original_file_name, signed_file_path):
    sql = "INSERT INTO signed_files (original_file_name, signed_file_path) VALUES (%s, %s)"
    val = (original_file_name, signed_file_path)
    db_cursor.execute(sql, val)
    db_connection.commit()


@app.route("/sign", methods=["POST"])
def sign_file():
    key_files = request.files.getlist("keyPath")
    files = request.files.getlist("file")
    password = request.form["password"]

    for file in key_files:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        key_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    for file in files:
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

    returnfile = sign_file_gos(key_path, password, file_path)

    response = make_response(returnfile)
    response.headers["Content-Disposition"] = 'attachment; filename="{}"'.format(
        os.path.basename(file_path)
    )
    return response


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

    save_to_database(os.path.basename(file), decoded_file_path)

    if os.path.exists(key):
        os.remove(key)
    if os.path.exists(file):
        os.remove(file)

    return decoded_data


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

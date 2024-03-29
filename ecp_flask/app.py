import os
import json
import base64
import requests
from flask import Flask, request, make_response, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/sign", methods=["POST"])
def sign_file():
    app.config["UPLOAD_FOLDER"] = ""  # Папка, куда сохранять загруженные файлы
    key_files = request.files.getlist("keyPath")
    files = request.files.getlist("file")
    password = request.form["password"]

    # Обработка загруженных файлов
    for file in key_files:
        # Сохраняем файлы в нужном месте или обрабатываем их
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        key_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
    for file in files:
        # Сохраняем файлы в нужном месте или обрабатываем их
        file.save(os.path.join(app.config["UPLOAD_FOLDER"], file.filename))
        file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)

    returnfile = sign_file_gos(key_path, password, file_path)

    response = make_response(returnfile)
    response.headers[
        "Content-Disposition"
    ] = 'attachment; filename="your_filename.extension"'

    return response


def sign_file_gos(key, password, file):
    base64_key_string = get_base_64_key_string(key)
    print(f"file --------------------------- {file}")
    with open(file, "rb") as files:  # Открываем файловый поток из объекта FileStorage
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

    with open("decoded_file.cms", "wb") as f:
        f.write(decoded_data)
    if os.path.exists(key):
        os.remove(key)
    if os.path.exists(file):
        os.remove(file)
    return decoded_data


def get_base_64_key_string(key) -> str:
    with open(key, "rb") as file:  # Открываем файловый поток из объекта FileStorage
        key_contents = file.read()
    encoded_key = base64.b64encode(key_contents)
    base64_key_string = encoded_key.decode("utf-8")

    return base64_key_string


@app.route("/verify", methods=["POST", "GET"])
def verify_data():
    revocation_check = ["OCSP"]

    file_path = "/var/www/ecp.medkrmu/KRMU-main/decoded_file.cms"

    with open(file_path, "rb") as f:
        data_to_verify = base64.b64encode(f.read()).decode("utf-8")

    url = "http://localhost:14579/cms/verify"

    headers = {"Content-Type": "application/json"}

    payload = {"revocationCheck": revocation_check, "cms": data_to_verify}

    payload_json = json.dumps(payload)

    response = requests.post(url, data=payload_json, headers=headers)

    response_data = response.json()

    return jsonify(response_data)


if __name__ == "__main__":
    app.run(debug=True)

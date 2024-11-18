import os
import io
import base64
import logging
import requests
import pandas as pd
from flask_cors import CORS
from celery_config import app, celery
from flask import jsonify, render_template, request, send_file
from utils import (
    get_packages,
    db_connection,
    execute_query,
    initialize_database,
    db_connection_certificate,
)
import logger

logger = logging.getLogger(__name__)


CORS(app)

HOST_URL = "https://ecp.medkrmu.kz/"

app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


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


@app.route("/sign", methods=["POST"])
def sign_file():
    logger.info("Received sign_file request")

    key_files = request.files.getlist("keyPath")
    password = request.form.get("password")
    package = request.form.get("package")

    logger.info(
        f"Received form data - Key files: {key_files}, Password: {'*' * len(password) if password else None}, Package: {package}"
    )

    if not key_files or not key_files[0]:
        logger.error("Key file is missing")
        return jsonify({"error": "Key file is missing"}), 400

    if not password:
        logger.error("Password is missing")
        return jsonify({"error": "Password is missing"}), 400

    key_path = os.path.join(app.config["UPLOAD_FOLDER"], key_files[0].filename)
    logger.info(f"Saving key file to: {key_path}")
    key_files[0].save(key_path)

    file_paths = []

    if package:
        logger.info(f"Package for path: {package}")

        directory = (
            f"/var/www/kirill/certificates.medkrmu/cert_date_base/{package}/pdf/"
        )
        signed_folder = directory
        logger.info(f"Looking for files in directory {directory}")
        os.makedirs(directory, exist_ok=True)

        for filename in os.listdir(directory):
            if filename.endswith(".pdf"):
                file_path = os.path.join(directory, filename)
                file_paths.append(file_path)
                logger.info(f"Found file to sign: {file_path}")

        if not file_paths:
            logger.error("No files to sign in the package directory")
            if os.path.exists(key_path):
                os.remove(key_path)
                logger.info(f"Removed key file: {key_path}")
            return jsonify({"error": "No files to sign in the package"}), 400

    else:
        files = request.files.getlist("file")
        signed_folder = os.path.join(app.root_path, "signed")
        logger.info(f"Manual file mode: Saving signed files to {signed_folder}")
        os.makedirs(signed_folder, exist_ok=True)

        for file in files:
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], file.filename)
            logger.info(f"Saving file to: {file_path}")
            file.save(file_path)
            file_paths.append(file_path)

    if not file_paths:
        logger.error("No files to sign")
        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")
        return jsonify({"error": "No files to sign"}), 400

    logger.info(f"Starting signing process for files: {file_paths}")

    task = celery.send_task(
        "celery_worker.async_sign_file",
        args=[key_path, password, file_paths, package, signed_folder],
    )

    logger.info(f"Task for signing files started with task ID: {task.id}")

    return jsonify({"message": "Signing process started", "task_id": task.id}), 202


@app.route("/task_status/<task_id>")
def get_task_status(task_id):
    task = celery.AsyncResult(task_id)

    response = {
        "task_id": task_id,
    }

    if task.state == "PENDING":
        response["status"] = "Pending"

    elif task.state == "SUCCESS":
        response["status"] = "Success"

    elif task.state == "FAILURE":
        response["status"] = "Error"
        response["error"] = str(task.info)

    else:
        response["status"] = task.state

    return jsonify(response)


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


initialize_database()

if __name__ == "__main__":
    initialize_database()
    app.run(host="0.0.0.0", port="5002", debug=app.config["DEBUG"])

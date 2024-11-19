from celery import shared_task
from utils import (
    merge_pdfs,
    process_pdf,
    sign_file_gos,
    save_to_database,
    print_verification_info,
    get_verification_result,
    db_connection_certificate,
)
import os
import logging

logger = logging.getLogger(__name__)


@shared_task(name="celery_worker.async_sign_file")
def async_sign_file(key_path, password, file_paths, package, signed_folder):
    logger.info(
        f"Starting async_sign_file with key_path={key_path}, password=****, file_paths={file_paths}, package={package}"
    )
    signed_files = []
    try:
        for file_path in file_paths:
            logger.info(f"Processing file: {file_path}")

            signed_pdf, file_id = sign_file_gos(key_path, password, file_path)
            if not signed_pdf or not file_id:
                logger.error(f"Signing failed for file: {file_path}")
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Signing failed",
                )
                raise ValueError(f"Signing failed for file: {file_path}")

            logger.info(f"File signed successfully: {file_path}, file_id: {file_id}")

            verification_result = get_verification_result(file_id)
            verification_info = print_verification_info(verification_result)

            if not verification_info:
                logger.error(
                    f"Verification failed for file: {file_path}. Missing ORGANIZATION permission."
                )
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Verification failed: Missing ORGANIZATION permission.",
                )
                raise ValueError("Invalid ECP key: Missing required ORGANIZATION permission.")

            logger.info(f"Verification info obtained for file: {file_path}")

            merged_pdf_content = process_pdf(signed_pdf, verification_info)
            merged_pdf = merge_pdfs(file_path, merged_pdf_content)

            final_signed_pdf, final_file_id = sign_file_gos(key_path, password, merged_pdf)
            if not final_signed_pdf or not final_file_id:
                logger.error(f"Final signing failed for file: {file_path}")
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Final signing failed",
                )
                raise ValueError(f"Final signing failed for file: {file_path}")

            logger.info(
                f"Final file signed successfully: {file_path}, final_file_id: {final_file_id}"
            )

            old_file_path = f"{file_path}.old"
            os.rename(file_path, old_file_path)
            logger.info(f"Renamed original file to: {old_file_path}")

            original_filename = os.path.basename(file_path)
            signed_file_path = os.path.join(signed_folder, original_filename)
            with open(signed_file_path, "wb") as f:
                f.write(final_signed_pdf)
            logger.info(f"Saved signed file to: {signed_file_path}")

            save_to_database(original_filename, signed_file_path, "async_sign_file", "OK")

            signed_files.append(
                {
                    "filename": os.path.splitext(original_filename)[0],
                    "signed_pdf": final_signed_pdf,
                }
            )

        if package and signed_files:
            filenames = [file["filename"] for file in signed_files]
            if filenames:
                try:
                    placeholders = ", ".join(["%s"] * len(filenames))
                    update_query = (
                        f"UPDATE certificate SET signed_status = 2 WHERE id IN ({placeholders})"
                    )
                    with db_connection_certificate.cursor() as cursor:
                        cursor.execute(update_query, filenames)
                        db_connection_certificate.commit()
                    update_package_query = (
                        "UPDATE packages SET signed_status = 2 WHERE package_name = %s"
                    )
                    with db_connection_certificate.cursor() as cursor:
                        cursor.execute(update_package_query, (package,))
                        db_connection_certificate.commit()
                    logger.info(
                        f"Updated signed_status in certificate table for filenames: {filenames}"
                    )
                except Exception as err:
                    logger.error(f"Some error happened during process: {err}")
                    raise

            else:
                logger.warning("No filenames found in signed_files to update the database.")

        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")

        logger.info("All files processed successfully.")
        return {"message": "All files processed successfully", "files": signed_files}
    except Exception as e:
        logger.error(f"Error during signing: {str(e)}")
        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")
        raise RuntimeError(
            "An error has occurred, please check the validity of the data or contact the administrator"
        )


from celery import shared_task
from utils import (
    merge_pdfs,
    process_pdf,
    sign_file_gos,
    save_to_database,
    print_verification_info,
    get_verification_result,
    db_connection_certificate,
)
import os
import logging

logger = logging.getLogger(__name__)


@shared_task(name="celery_worker.async_sign_file")
def async_sign_file(key_path, password, file_paths, package, signed_folder):
    logger.info(
        f"Starting async_sign_file with key_path={key_path}, password=****, file_paths={file_paths}, package={package}"
    )
    signed_files = []
    try:
        for file_path in file_paths:
            logger.info(f"Processing file: {file_path}")

            signed_pdf, file_id = sign_file_gos(key_path, password, file_path)
            if not signed_pdf or not file_id:
                logger.error(f"Signing failed for file: {file_path}")
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Signing failed",
                )
                raise ValueError(f"Signing failed for file: {file_path}")

            logger.info(f"File signed successfully: {file_path}, file_id: {file_id}")

            verification_result = get_verification_result(file_id)
            verification_info = print_verification_info(verification_result)

            if not verification_info:
                logger.error(
                    f"Verification failed for file: {file_path}. Missing ORGANIZATION permission."
                )
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Verification failed: Missing ORGANIZATION permission.",
                )
                raise ValueError("Invalid ECP key: Missing required ORGANIZATION permission.")

            logger.info(f"Verification info obtained for file: {file_path}")

            merged_pdf_content = process_pdf(signed_pdf, verification_info)
            merged_pdf = merge_pdfs(file_path, merged_pdf_content)

            final_signed_pdf, final_file_id = sign_file_gos(key_path, password, merged_pdf)
            if not final_signed_pdf or not final_file_id:
                logger.error(f"Final signing failed for file: {file_path}")
                save_to_database(
                    os.path.basename(file_path),
                    file_path,
                    "async_sign_file",
                    "Final signing failed",
                )
                raise ValueError(f"Final signing failed for file: {file_path}")

            logger.info(
                f"Final file signed successfully: {file_path}, final_file_id: {final_file_id}"
            )

            old_file_path = f"{file_path}.old"
            os.rename(file_path, old_file_path)
            logger.info(f"Renamed original file to: {old_file_path}")

            original_filename = os.path.basename(file_path)
            signed_file_path = os.path.join(signed_folder, original_filename)
            with open(signed_file_path, "wb") as f:
                f.write(final_signed_pdf)
            logger.info(f"Saved signed file to: {signed_file_path}")

            save_to_database(original_filename, signed_file_path, "async_sign_file", "OK")

            signed_files.append(
                {
                    "filename": os.path.splitext(original_filename)[0],
                    "signed_pdf": final_signed_pdf,
                }
            )

        if package and signed_files:
            filenames = [file["filename"] for file in signed_files]
            if filenames:
                try:
                    placeholders = ", ".join(["%s"] * len(filenames))
                    update_query = (
                        f"UPDATE certificate SET signed_status = 2 WHERE id IN ({placeholders})"
                    )
                    with db_connection_certificate.cursor() as cursor:
                        cursor.execute(update_query, filenames)
                        db_connection_certificate.commit()
                    update_package_query = (
                        "UPDATE packages SET signed_status = 2 WHERE package_name = %s"
                    )
                    with db_connection_certificate.cursor() as cursor:
                        cursor.execute(update_package_query, (package,))
                        db_connection_certificate.commit()
                    logger.info(
                        f"Updated signed_status in certificate table for filenames: {filenames}"
                    )
                except Exception as err:
                    logger.error(f"Some error happened during process: {err}")
                    raise

            else:
                logger.warning("No filenames found in signed_files to update the database.")

        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")

        logger.info("All files processed successfully.")
        return {"message": "All files processed successfully", "files": signed_files}
    except Exception as e:
        logger.error(f"Error during signing: {str(e)}")
        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")
        raise RuntimeError(
            "An error has occurred, please check the validity of the data or contact the administrator"
        )

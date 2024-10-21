from celery import shared_task
from utils import (
    merge_pdfs,
    process_pdf,
    sign_file_gos,
    save_to_database,
    rename_pdfs_to_old,  
    print_verification_info,
    get_verification_result,
    db_connection_certificate,
)
import os
import logging

logger = logging.getLogger(__name__)

@shared_task(name='celery_worker.async_sign_file')
def async_sign_file(key_path, password, file_paths, package, signed_folder):
    logger.info(f"Starting async_sign_file with key_path={key_path}, password=****, file_paths={file_paths}, package={package}")
    try:
        rename_pdfs_to_old(signed_folder)
        logger.info(f"Renamed original PDFs to .old in directory: {signed_folder}")

        renamed_file_paths = []
        for file_path in file_paths:
            directory, filename = os.path.split(file_path)
            old_filename = f"{filename}.old"
            old_file_path = os.path.join(directory, old_filename)
            if os.path.exists(old_file_path):
                renamed_file_paths.append(old_file_path)
            else:
                logger.error(f"Renamed file not found: {old_file_path}")
                continue

        signed_files = []
        processed_files = []

        for file_path in renamed_file_paths:
            try:
                logger.info(f"Processing file: {file_path}")
                signed_pdf, file_id = sign_file_gos(key_path, password, file_path)
                if not signed_pdf or not file_id:
                    logger.error(f"Signing failed for file: {file_path}")
                    continue

                logger.info(f"File signed successfully: {file_path}, file_id: {file_id}")

                verification_info = print_verification_info(get_verification_result(file_id))
                if verification_info:
                    logger.info(f"Verification info obtained for file: {file_path}")

                    merged_pdf_content = process_pdf(signed_pdf, verification_info)

                    merged_pdf = merge_pdfs(file_path, merged_pdf_content)

                    final_signed_pdf, final_file_id = sign_file_gos(key_path, password, merged_pdf)
                    if not final_signed_pdf or not final_file_id:
                        logger.error(f"Final signing failed for file: {file_path}")
                        continue

                    logger.info(f"Final file signed successfully: {file_path}, final_file_id: {final_file_id}")

                    original_filename = os.path.basename(file_path).replace('.pdf.old', '.pdf')
                    signed_file_path = os.path.join(signed_folder, original_filename)

                    processed_files.append({
                        "signed_file_path": signed_file_path,
                        "signed_pdf": final_signed_pdf,
                        "original_filename": original_filename,
                    })

                    signed_files.append({
                        "filename": os.path.splitext(original_filename)[0],
                        "signed_pdf": final_signed_pdf
                    })

                    save_to_database(
                        original_filename,
                        signed_file_path,
                        "async_sign_file",
                        "OK"
                    )
                else:
                    logger.error(f"Verification info could not be retrieved for file: {file_path}")
                    continue
            except Exception as e:
                logger.exception(f"Error processing file {file_path}: {str(e)}")
                continue

        for processed_file in processed_files:
            try:
                signed_file_path = processed_file['signed_file_path']
                final_signed_pdf = processed_file['signed_pdf']

                with open(signed_file_path, 'wb') as f:
                    f.write(final_signed_pdf)
                logger.info(f"Saved signed file to: {signed_file_path}")
            except Exception as e:
                logger.exception(f"Error finalizing file {processed_file['original_filename']}: {str(e)}")

        if os.path.exists(key_path):
            os.remove(key_path)
            logger.info(f"Removed key file: {key_path}")

        if package and signed_files:
            filenames = [file['filename'] for file in signed_files]
            if filenames:
                placeholders = ', '.join(['%s'] * len(filenames))
                update_query = f"UPDATE certificate SET signed_status = 2 WHERE id IN ({placeholders})"
                with db_connection_certificate.cursor() as cursor:
                    cursor.execute(update_query, filenames)
                    db_connection_certificate.commit()
                update_package_query = "UPDATE packages SET signed_status = 2 WHERE package_name = %s"
                with db_connection_certificate.cursor() as cursor:
                    cursor.execute(update_package_query, (package,))
                    db_connection_certificate.commit()
                logger.info(f"Updated signed_status in certificate table for id: {filenames}")
            else:
                logger.warning("No filenames found in signed_files to update the database.")

        logger.info("All files signed successfully.")
        return {"message": "All files signed successfully", "files": signed_files}
    except Exception as e:
        logger.exception(f"Error during signing: {str(e)}")
        if os.path.exists(key_path):
            os.remove(key_path)
        raise

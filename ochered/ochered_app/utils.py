import os
import qrcode
from django.conf import settings

def generate_qr_code():
    server_domain_ip = settings.SERVER_DOMAIN_IP

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )

    qr.add_data(server_domain_ip + "/register_ticket/")
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    media_path = settings.MEDIA_ROOT
    qr_code_path = os.path.join(media_path, "qr-code.png")

    if os.path.exists(qr_code_path):
        os.remove(qr_code_path)

    img.save(qr_code_path)

    return qr_code_path

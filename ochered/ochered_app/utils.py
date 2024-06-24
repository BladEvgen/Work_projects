import qrcode
from PIL import Image, ImageDraw, ImageFont
from django.conf import settings
import os


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

    draw = ImageDraw.Draw(img)

    font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=20)

    text = f"Referer: {server_domain_ip}/register_ticket/"
    draw.text((10, img.size[1] - 30), text, fill="black", font=font)

    media_path = settings.MEDIA_ROOT
    qr_code_path = os.path.join(media_path, "qr-code.png")

    if os.path.exists(qr_code_path):
        os.remove(qr_code_path)

    img.save(qr_code_path)

    return qr_code_path

import os
import re
import qrcode
from django.conf import settings


def generate_qr_code():
    server_domain_ip = settings.SERVER_DOMAIN_IP

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=20,
        border=4,
    )

    qr.add_data(server_domain_ip + "/register_ticket/")
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    min_size = 500
    if img.size[0] < min_size or img.size[1] < min_size:
        img = img.resize(
            (max(min_size, img.size[0]), max(min_size, img.size[1])), resample=0
        )

    media_path = settings.MEDIA_ROOT
    qr_code_path = os.path.join(media_path, "qr-code.png")

    if os.path.exists(qr_code_path):
        os.remove(qr_code_path)

    img.save(qr_code_path)

    return qr_code_path


def password_check(password: str) -> bool:
    """
    Проверяет, соответствует ли пароль требованиям сложности системы.

    Эта функция проверяет строку пароля на основе следующих критериев:

        - Минимальная длина 8 символов.
        - Содержит хотя бы одну заглавную букву (A-Z)
        - Содержит хотя бы одну строчную букву (a-z)
        - Содержит хотя бы одну цифру (0-9)
        - Содержит хотя бы один специальный символ из следующего набора: #?!@$%^&*-

    Args:
        пароль (str): строка пароля, которую необходимо проверить.

    Returns:
        bool: True, если пароль соответствует всем требованиям сложности, в противном случае — False
    """
    return bool(
        re.match(
            r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).{8,}$", password
        )
    )

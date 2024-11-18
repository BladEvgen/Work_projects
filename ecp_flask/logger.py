import os
import logging
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "log")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


def get_log_filename():
    current_time = datetime.now()
    return os.path.join(LOG_DIR, f'log-{current_time.strftime("%Y-%m-%d_%H")}.log')


log_filename = get_log_filename()

file_handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")

formatter = logging.Formatter(
    "{asctime} | {levelname} | {message}", style="{", datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)

logger = logging.getLogger()

DEBUG = True
if DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

logger.addHandler(file_handler)

current_hour = datetime.now().hour


def rotate_log_file():
    global current_hour, logger
    now = datetime.now()
    if now.hour != current_hour:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        current_hour = now.hour
        log_filename = get_log_filename()
        file_handler = logging.FileHandler(log_filename, mode="a", encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        logger.info(f"Log rotated to {log_filename}")


def log_example_messages():
    rotate_log_file()
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")

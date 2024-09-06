import os
import socket
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

host_names = ["RogStrix", "MacBook-Pro.local", "MacbookPro"]
DEBUG = True if socket.gethostname() in host_names else False
DOTENV_PATH = BASE_DIR / ".env"
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)

SECRET_KEY = os.getenv("SECRET_KEY")
SERVER_DOMAIN_IP = os.getenv("SERVER_DOMAIN_IP")

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 МБ
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 МБ

DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000000

if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = ["queue.krmu.edu.kz", "dot.medkrmu.kz", "localhost", "127.0.0.1"]

CSRF_TRUSTED_ORIGINS = [
    "https://queue.krmu.edu.kz",
    "https://dot.medkrmu.kz",
    "http://localhost:8000",
]

INSTALLED_APPS = [
    # Installed apps
    "daphne",
    "channels",
    "grappelli",
    "corsheaders",
    "django_extensions",
    # Stadnart
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # App
    "ochered_app",
]

CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOWED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://127.0.0.1:5002",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8000",
    "http://localhost:5002",
    "https://dot.medkrmu.kz",
    "https://queue.krmu.edu.kz",
]

MIDDLEWARE = [
    "ochered_app.middleware.LogAccessMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "django_settings.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            BASE_DIR / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "ochered_app.context_processors.current_year",
            ],
        },
    },
]

WSGI_APPLICATION = "django_settings.wsgi.application"
ASGI_APPLICATION = "django_settings.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    },
}

if DEBUG:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("db_name"),
            "USER": os.getenv("db_user"),
            "PASSWORD": os.getenv("db_password"),
            "HOST": os.getenv("db_host"),
            "PORT": os.getenv("db_port"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "ru"

TIME_ZONE = "Asia/Almaty"

USE_I18N = True

USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = Path(BASE_DIR / "staticroot")
STATICFILES_DIRS = [
    Path(BASE_DIR, "static"),
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "static/media"

LOG_DIR = os.path.join(BASE_DIR, "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M",
        },
    },
    "handlers": {
        "file": {
            "level": "INFO" if DEBUG else "WARNING",
            "class": "logging.FileHandler",
            "filename": os.path.join(
                LOG_DIR, f'log-{datetime.now().strftime("%Y-%m-%d_%H")}.log'
            ),
            "formatter": "verbose",
        },
    },
    "loggers": {
        "": {
            "handlers": ["file"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
        "django": {
            "handlers": ["file"],
            "level": "INFO" if DEBUG else "WARNING",
            "propagate": False,
        },
    },
}

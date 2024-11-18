import os
from flask import Flask
from celery import Celery


def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config["result_backend"],
        broker=app.config["CELERY_BROKER_URL"],
        include=["celery_worker"],
    )
    celery.conf.update(app.config)
    celery.conf.update(
        broker_connection_retry_on_startup=True,  # Включить повторное подключение при старте
        broker_connection_retry=True,  # Включить повторное подключение при потере связи
        broker_connection_max_retries=5,  # Количество попыток повторного подключения
        broker_connection_timeout=60,  # Таймаут подключения в секундах
        task_acks_late=True,  # Включить подтверждение задач после выполнения
    )
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask
    return celery


def create_app():
    app = Flask(__name__)
    app.config.update(
        CELERY_BROKER_URL="redis://localhost:6379/1",
        result_backend="redis://localhost:6379/1",
        UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), "static", "uploads"),
        DEBUG=True,
    )
    return app


app = create_app()
celery = make_celery(app)

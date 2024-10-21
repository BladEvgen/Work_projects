import os
from flask import Flask
from celery import Celery

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['result_backend'],  
        broker=app.config['CELERY_BROKER_URL'],
        include=['celery_worker']
    )
    celery.conf.update(app.config)
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
        CELERY_BROKER_URL='redis://localhost:6379/0',
        result_backend='redis://localhost:6379/0',
        UPLOAD_FOLDER=os.path.join(os.path.dirname(__file__), "static", "uploads"),
        DEBUG=True
    )
    return app

app = create_app()
celery = make_celery(app)

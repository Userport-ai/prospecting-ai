from app import create_app

# This module is needed to initialize Celery worker from command line and access Celery App object.

flask_app = create_app()
celery_app = flask_app.extensions["celery"]

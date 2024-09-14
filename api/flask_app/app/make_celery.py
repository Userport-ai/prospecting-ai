import celery.signals
from app import create_app

# This module is needed to initialize Celery worker from command line and access Celery App object.


@celery.signals.setup_logging.connect
def config_loggers(*args, **kwags):
    """This signals handler is needed otherwise logs on GKE are displayed as error even for INFO logs."""


flask_app = create_app()
celery_app = flask_app.extensions["celery"]

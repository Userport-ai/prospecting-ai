import celery.signals
from app import create_app, load_env_vars, setup_logging

# This module is needed to initialize Celery worker from command line and access Celery App object.


@celery.signals.setup_logging.connect
def config_loggers(*args, **kwags):
    """Setup logging for Celery app to match Flask app."""
    load_env_vars()
    setup_logging()


flask_app = create_app()
celery_app = flask_app.extensions["celery"]

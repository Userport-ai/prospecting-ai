import os
from flask import Flask
from app import flask_api
from celery import Celery, Task
from logging.config import dictConfig
import firebase_admin
from dotenv import load_dotenv


def setup_logging():
    """Setup logging for the app based on environemnt.

    In cloud, we want to use GCP Cloud Logging because it has a different handler.
    """
    flask_env = os.environ["FLASK_ENV"]
    if flask_env == "dev":
        # Local Logging configuration for the Flask app.
        dictConfig(
            {
                "version": 1,
                "formatters": {
                    "default": {
                        "format": "[%(asctime)s] [%(levelname)s | %(module)s] %(message)s",
                        "datefmt": "%B %d, %Y %H:%M:%S %Z",
                    },
                },
                "handlers": {
                    "console": {
                        "class": "logging.StreamHandler",
                        "formatter": "default",
                    },
                    "file": {
                        "class": "logging.FileHandler",
                        "filename": "userport.log",
                        "formatter": "default",
                    },
                },
                "root": {"level": "INFO", "handlers": ["console", "file"]},
            }
        )
    elif flask_env == "production":
        # Google Cloud Logging will setup Root Logger with the appropriate handler.
        # Reference: https://cloud.google.com/logging/docs/setup/python#write_logs_with_the_standard_python_logging_handler.
        # Cannot run locally since permissions not setup to write Logs to Cloud Logging resource.

        import google.cloud.logging
        # Instantiates a client
        client = google.cloud.logging.Client()
        # Retrieves a Cloud Logging handler based on the environment
        # you're running in and integrates the handler with the
        # Python logging module. By default this captures all logs
        # at INFO level and higher
        client.setup_logging()
    else:
        raise ValueError(
            f"Invalid flask env: {flask_env} value, cannot setup logging")


def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, task_cls=FlaskTask)
    celery_app.config_from_object(app.config["CELERY"])
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app


def load_env_vars():
    """Check if env is configured for dev or production and load additional env variables accordingly.

    Should be called during Flask app initialization so that env variables can be directly referenced from os module everywhere else.
    """
    # Loads environment variables from .env file if no path is specified.
    load_dotenv()
    flask_env = os.environ["FLASK_ENV"]
    if flask_env == "dev":
        load_dotenv(".env.dev")
    elif flask_env == "production":
        load_dotenv(".env.production")
    else:
        raise ValueError(f"Invalid FLASK_ENV value: {flask_env}")


def create_app():
    # First Env variables must be loaded so that rest of the app works.
    load_env_vars()

    # Setup logging according to the right environment.
    setup_logging()

    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    # Loads all env variables prefixed with FLASK_ into Flask object app.config automatically.
    # Env variables loaded include those from [1].env and [2].env.dev or .env.production based on which env is configured.
    # Reference: https://flask.palletsprojects.com/en/3.0.x/config/.
    app.config.from_prefixed_env()

    firebase_admin.initialize_app()
    app.register_blueprint(flask_api.bp)
    celery_init_app(app)
    return app

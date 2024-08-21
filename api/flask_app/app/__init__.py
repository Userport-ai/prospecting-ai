import os
from flask import Flask
from app import flask_api
from celery import Celery, Task
from logging.config import dictConfig
import firebase_admin

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env if no path specified.

# Logging configuration for the Flask app.
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
        "root": {"level": "DEBUG", "handlers": ["console", "file"]},
    }
)


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


def create_app():
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)

    # Check if env is configured for dev or production and load additional env variables accordingly.
    flask_env = os.getenv("FLASK_ENV")
    if flask_env == "dev":
        load_dotenv(".env.dev")
    elif flask_env == "production":
        load_dotenv(".env.production")
    else:
        raise ValueError(f"Invalid FLASK_ENV value: {flask_env}")

    # Loads all env variables prefixed with FLASK_ into app.config automatically.
    # Env variables loaded include those from [1].env and [2].env.dev or .env.production based on which env is configured.
    # Reference: https://flask.palletsprojects.com/en/3.0.x/config/.
    app.config.from_prefixed_env()

    firebase_admin.initialize_app()
    app.register_blueprint(flask_api.bp)
    celery_init_app(app)
    return app

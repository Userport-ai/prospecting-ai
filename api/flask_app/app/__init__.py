from flask import Flask
from app import flask_api

from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env.


def create_app(test_config=None):
    # create and configure the app
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='dev',
    )

    app.register_blueprint(flask_api.bp)

    return app

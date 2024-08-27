import os
from app import load_env_vars, setup_logging

# Load env vars and setup logging.
load_env_vars()
setup_logging()

auth_provider = "flower.views.auth.GoogleAuth2LoginHandler"
auth = os.environ["FLOWER_AUTH"]
oauth2_key = os.environ["FLOWER_OAUTH2_KEY"]
oauth2_secret = os.environ["FLOWER_OAUTH2_SECRET"]
oauth2_redirect_uri = os.environ["FLOWER_OAUTH2_REDIRECT_URI"]

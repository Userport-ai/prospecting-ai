import logging
from gunicorn.glogging import Logger
from app import load_env_vars, setup_logging


class GunicornLogger(Logger):
    def setup(self, cfg):
        super(GunicornLogger, self).setup(cfg)

        # Load env vars and setup logging.
        load_env_vars()
        setup_logging()

        # Get root logger and attach to Gunicorn.
        logger = logging.getLogger()
        self.access_log = logger
        self.error_log = logger


# Reference: https://docs.gunicorn.org/en/latest/settings.html#logger-class
logger_class = GunicornLogger

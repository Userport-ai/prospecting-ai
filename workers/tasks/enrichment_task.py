from abc import abstractmethod

from tasks.base import BaseTask
from utils.loguru_setup import logger


class AccountEnrichmentTask(BaseTask):
    """Base class for all tasks"""


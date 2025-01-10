from abc import abstractmethod

from tasks.base import BaseTask


class AccountEnrichmentTask(BaseTask):
    """Base class for all tasks"""

    @property
    @abstractmethod
    def enrichment_type(self) -> str:
        """
           Enrichment Type identifier
           Note: Make sure to keep it in sync with the @EnrichmentType enum in the AccountEnrichment model
           in Django
        """
        pass

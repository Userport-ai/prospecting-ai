import logging
from typing import Optional
from urllib.parse import urlparse
import tldextract

logger = logging.getLogger(__name__)


class UrlUtils:
    @staticmethod
    def get_domain(url: str):
        """Helper to return domain for given URL.

        For example: https://www.zuddle.com will return zuddle.com.
        """
        result = tldextract.extract(url)
        return f"{result.domain}.{result.suffix}"

    @staticmethod
    def are_account_linkedin_urls_same(account_url_1: Optional[str], account_url_2: Optional[str]) -> bool:
        """Returns true if the two Account LinkedIn URLs are equivalent.

        The reason why string match won't work always is because the URL can be stored differently
        in different systems. Ex. [1] https://www.linkedin.com/company/workable-software
        [2] http://linkedin.com/company/workable-software and [3] https://www.linkedin.com/company/workable-software/
        are 3 representations which are the same.
        """
        if not account_url_1 or not account_url_2:
            return False
        substr = "linkedin.com/company/"
        if (substr not in account_url_1) or (substr not in account_url_2):
            return False
        suffix_1 = account_url_1.split(substr)[1].split("/")
        suffix_2 = account_url_2.split(substr)[1].split("/")
        return suffix_1 == suffix_2

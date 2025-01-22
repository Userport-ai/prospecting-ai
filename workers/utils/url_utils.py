import logging
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)
class UrlUtils:
    @staticmethod
    def extract_domain(url: str) -> Optional[str]:
        """Extract domain from website URL."""
        try:
            parsed = urlparse(url.strip().lower())

            # Add scheme if missing
            if not parsed.scheme:
                parsed = urlparse(f"https://{url}")

            # Get domain from netloc
            domain = parsed.netloc

            # Remove www. prefix if present
            if domain.startswith("www."):
                domain = domain[4:]

            # Basic validation
            if not domain or "." not in domain:
                return None

            return domain

        except Exception as e:
            logger.error(f"Error extracting domain from URL {url}: {str(e)}")
            return None
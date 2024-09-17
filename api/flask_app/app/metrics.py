import os
from posthog import Posthog
from typing import Dict, Optional


class Metrics:
    """Helper to capture metrics for Flask app."""

    def __init__(self) -> None:
        """Should be called during flask app is initialized so env variables are loaded."""
        self.posthog = Posthog(os.environ["POSTHOG_PUBLIC_KEY"],
                               host=os.environ["POSTHOG_PUBLIC_HOST"])

    def capture(self, user_id: str, event_name: str, properties: Optional[Dict] = None):
        """Capture event for given user ID and event name. ID can be anything unique."""
        self.posthog.capture(distinct_id=user_id,
                             event=event_name, properties=properties)

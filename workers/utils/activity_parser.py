import json
import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from google.api_core.exceptions import ResourceExhausted
from markdownify import markdownify

from models.lead_activities import LinkedInActivity, ContentDetails, OpenAITokenUsage
from services.ai.ai_service import AIServiceFactory
from utils.retry_utils import RetryableError, RetryConfig, with_retry
from utils.loguru_setup import logger

GEMINI_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=2.0,
    max_delay=30.0,
    retryable_exceptions=[
        RetryableError,
        ResourceExhausted,
        ValueError,
        RuntimeError,
        TimeoutError,
        ConnectionError
    ]
)


class LinkedInActivityParser:
    """Parser for LinkedIn activities."""

    def __init__(self, person_name: str, company_name: str, company_description: str, person_role_title: str):
        """Initialize parser with context."""
        logger.info(f"Initializing LinkedInActivityParser for {person_name} at {company_name}")
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title

        try:
            self.model = AIServiceFactory().create_service("openai")
            logger.info("Successfully configured Gemini API")
        except Exception as e:
            logger.error(f"Failed to configure Gemini API: {str(e)}")
            raise

        self.system_prompt = self._create_system_prompt()
        logger.debug(f"System prompt created: {self.system_prompt[:100]}...")

    def _create_system_prompt(self) -> str:
        """Create system prompt for AI analysis."""
        return f"""You are analyzing LinkedIn activity for:
Person: {self.person_name}
Company: {self.company_name}
Role: {self.person_role_title}

Company Description: {self.company_description}

Analyze the content to extract:
1. Publishing date and metrics
2. Content summary and category
3. Company focus and relevance
4. Key people and products mentioned
5. Hashtags used"""

    @staticmethod
    def get_activities(person_linkedin_url: str, page_html: str, activity_type: LinkedInActivity.Type) -> List[LinkedInActivity]:
        """Extract activities from LinkedIn page HTML."""
        logger.info(f"Extracting activities for {person_linkedin_url} of type {activity_type}")

        if not page_html.strip():
            logger.warning("Empty page HTML provided")
            return []

        try:
            # Remove member tags containing logged in user info
            soup = BeautifulSoup(page_html, "html.parser")
            member_tags = soup.find_all("div", class_="member")
            logger.debug(f"Found {len(member_tags)} member tags to remove")
            for tag in member_tags:
                tag.clear()

            # Convert to markdown
            page_md = markdownify(str(soup))
            logger.debug(f"Converted HTML to markdown, length: {len(page_md)}")

            # Split into individual activities
            content_list: List[str] = re.split(r'Feed post number \d*', page_md)
            logger.info(f"Found {len(content_list) - 1} potential activities")

            activities = []
            for i, content in enumerate(content_list):
                if i == 0:  # Skip header
                    continue

                try:
                    activity = LinkedInActivity(
                        person_linkedin_url=person_linkedin_url,
                        activity_url=LinkedInActivityParser._get_activity_url(
                            person_linkedin_url=person_linkedin_url,
                            activity_type=activity_type
                        ),
                        type=activity_type,
                        content_md=content
                    )
                    activities.append(activity)
                    logger.debug(f"Successfully created activity {i} with content length: {len(content)}")
                except Exception as e:
                    logger.error(f"Failed to create activity {i}: {str(e)}")

            logger.info(f"Successfully extracted {len(activities)} activities")
            return activities

        except Exception as e:
            logger.error(f"Error in get_activities: {str(e)}", exc_info=True)
            return []

    @staticmethod
    def _get_activity_url(person_linkedin_url: str, activity_type: LinkedInActivity.Type) -> str:
        """Get URL for activity type."""
        base = f"{person_linkedin_url}/recent-activity"
        if activity_type == LinkedInActivity.Type.POST:
            return f"{base}/all"
        elif activity_type == LinkedInActivity.Type.COMMENT:
            return f"{base}/comments"
        elif activity_type == LinkedInActivity.Type.REACTION:
            return f"{base}/reactions"
        else:
            raise ValueError(f"Invalid activity type: {activity_type}")

    async def parse_v2(self, activity: LinkedInActivity) -> Optional[ContentDetails]:
        """Parse LinkedIn activity into structured content."""
        logger.info(f"Starting parse_v2 for activity ID: {activity.id}")

        try:
            content = ContentDetails(
                url=activity.activity_url,
                person_name=self.person_name,
                company_name=self.company_name,
                person_role_title=self.person_role_title,
                linkedin_activity_ref_id=activity.id,
                linkedin_activity_type=activity.type,
                processing_status=ContentDetails.ProcessingStatus.NEW
            )
            logger.debug(f"Created ContentDetails object for activity {activity.id}")

            # Extract publish date
            logger.debug("Attempting to extract publish date")
            publish_date = await self._extract_date(activity.content_md)
            if not publish_date:
                logger.warning(f"Failed to extract publish date for activity {activity.id}")
                content.processing_status = ContentDetails.ProcessingStatus.FAILED_MISSING_PUBLISH_DATE
                return content

            content.publish_date = publish_date
            content.publish_date_readable_str = publish_date.strftime("%d %B, %Y")
            logger.debug(f"Extracted publish date: {content.publish_date_readable_str}")

            # Check if content is stale
            cutoff_date = datetime.utcnow() - relativedelta(months=15)
            if publish_date < cutoff_date:
                logger.info(f"Content is stale. Publish date: {publish_date}, Cutoff: {cutoff_date}")
                content.processing_status = ContentDetails.ProcessingStatus.FAILED_STALE_PUBLISH_DATE
                return content

            tokens_used = OpenAITokenUsage(
                operation_tag="activity_processing",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                total_cost_in_usd=0.0
            )

            # Extract content details
            logger.debug("Analyzing content with Gemini")
            response = await self._analyze_content(activity.content_md)
            if not response:
                logger.error("Failed to get response from content analysis")
                return None

            logger.debug(f"Content analysis response: {json.dumps(response, indent=2)}")

            # Update content object with response data
            content.detailed_summary = response.get("detailed_summary")
            content.concise_summary = response.get("concise_summary")
            content.one_line_summary = response.get("one_line_summary")
            content.category = response.get("category")
            content.category_reason = response.get("category_reason")
            content.focus_on_company = response.get("focus_on_company", False)
            content.focus_on_company_reason = response.get("focus_on_company_reason")

            # Extract people and products if company-focused
            if content.focus_on_company:
                logger.debug("Content is company-focused, extracting people and products")
                people_products = await self._extract_people_and_products(activity.content_md)
                logger.debug(f"People and products response: {json.dumps(people_products, indent=2)}")

                content.main_colleague = people_products.get("main_colleague")
                content.main_colleague_reason = people_products.get("colleague_reason")
                content.product_associations = people_products.get("products", [])

            # Extract engagement metrics and metadata
            logger.debug("Extracting metadata")
            metadata = await self._extract_metadata(activity.content_md)
            logger.debug(f"Metadata response: {json.dumps(metadata, indent=2)}")

            content.author = metadata.get("author")
            content.author_type = metadata.get("author_type")
            content.author_linkedin_url = metadata.get("author_linkedin_url")
            content.hashtags = metadata.get("hashtags", [])
            content.num_linkedin_reactions = metadata.get("reactions")
            content.num_linkedin_comments = metadata.get("comments")
            content.num_linkedin_reposts = metadata.get("reposts")

            content.processing_status = ContentDetails.ProcessingStatus.COMPLETE
            content.openai_tokens_used = tokens_used

            logger.info(f"Successfully completed parsing activity {activity.id}")
            return content

        except Exception as e:
            logger.error(f"Error in parse_v2 for activity {activity.id}: {str(e)}", exc_info=True)
            return None

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_analyze_content")
    async def _analyze_content(self, content_md: str) -> Dict[str, Any]:
        """Analyze content using Gemini."""
        logger.debug("Starting content analysis with Gemini")
        try:
            prompt = f"""Analyze this LinkedIn activity:

{content_md}

Provide a structured analysis with:
1. Detailed summary of the content (2-3 paragraphs)
2. Concise one-paragraph summary
3. One line summary
4. Content category and reason for categorization
5. Whether this is related to {self.company_name} and why
6. Any company products mentioned or discussed

Return as JSON with these fields:
{{
    "detailed_summary": string,
    "concise_summary": string,
    "one_line_summary": string,
    "category": string (one of: personal_thoughts, industry_update, company_news, product_update, social_update, other),
    "category_reason": string,
    "focus_on_company": boolean,
    "focus_on_company_reason": string,
    "products": [string]
}}"""

            logger.debug(f"Sending prompt to Gemini (length: {len(prompt)})")
            return await self.model.generate_content(prompt)

        except Exception as e:
            logger.error(f"Error in _analyze_content: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_extract_date")
    async def _extract_date(self, content_md: str) -> Optional[datetime]:
        """Extract publish date from content."""
        try:
            prompt = f"""Extract the publish date from this LinkedIn activity:

{content_md}

Find date format like: 4h, 5d, 1mo, 2yr, 3w
Return just the date string, nothing else."""

            response = await self.model.generate_content(prompt, is_json=False)

            date_str = response.strip()
            return self._parse_relative_date(date_str)

        except Exception as e:
            logger.error(f"Error extracting date: {str(e)}", exc_info=True)
            return None

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_extract_people_and_products")
    async def _extract_people_and_products(self, content_md: str) -> Dict[str, Any]:
        """Extract mentioned people and products."""
        try:
            prompt = f"""Analyze the following LinkedIn activity for people and products:

    {content_md}

    1. Identify the main colleague from {self.company_name} mentioned or discussed
    2. List any products from {self.company_name} mentioned

    Return as JSON:
    {{
            "main_colleague": string or null,
        "colleague_reason": string,
        "products": [string]
    }}"""

            response = await self.model.generate_content(prompt)
            return response

        except Exception as e:
            logger.error(f"Error extracting people and products: {str(e)}", exc_info=True)
            return {}

    @with_retry(retry_config=GEMINI_RETRY_CONFIG, operation_name="_extract_metadata")
    async def _extract_metadata(self, content_md: str) -> Dict[str, Any]:
        """Extract post metadata like author, hashtags, metrics."""
        try:
            prompt = f"""Extract metadata from this LinkedIn activity:

    {content_md}

    Return as JSON:
    {{
            "author": string,
        "author_type": "person" or "company",
        "author_linkedin_url": string,
        "hashtags": [string],
        "reactions": number or null,
        "comments": number or null,
        "reposts": number or null
    }}"""

            response = await self.model.generate_content(prompt)
            return response

        except Exception as e:
            logger.error(f"Error extracting metadata: {str(e)}", exc_info=True)
            return {}

    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative date string into datetime."""
        logger.debug(f"Parsing relative date: {date_str}")
        now = datetime.utcnow()

        patterns = {
            r'(\d+)h': lambda x: timedelta(hours=int(x)),
            r'(\d+)d': lambda x: timedelta(days=int(x)),
            r'(\d+)w': lambda x: timedelta(weeks=int(x)),
            r'(\d+)mo': lambda x: relativedelta(months=int(x)),
            r'(\d+)y': lambda x: relativedelta(years=int(x)),
            r'(\d+)yr': lambda x: relativedelta(years=int(x))
        }

        for pattern, delta_func in patterns.items():
            match = re.match(pattern, date_str)
            if match:
                value = match.group(1)
                result = now - delta_func(value)
                logger.debug(f"Matched pattern {pattern}, value {value}, result: {result}")
                return result

        logger.warning(f"No matching pattern found for date string: {date_str}")
        return None

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from AI response with error handling."""
        logger.debug(f"Parsing JSON response (length: {len(response)})")
        try:
            # Clean response text
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            result = json.loads(text)
            logger.debug(f"Successfully parsed JSON with keys: {list(result.keys())}")
            return result

        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}", exc_info=True)
            return {}

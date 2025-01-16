import os
import re
import logging
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
from markdownify import markdownify
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

import google.generativeai as genai
from models import LinkedInActivity, ContentDetails, OpenAITokenUsage

logger = logging.getLogger(__name__)

class LinkedInActivityParser:
    """Parser for LinkedIn activities."""

    def __init__(self, person_name: str, company_name: str, company_description: str, person_role_title: str):
        """Initialize parser with context."""
        self.person_name = person_name
        self.company_name = company_name
        self.company_description = company_description
        self.person_role_title = person_role_title

        self.GEMINI_API_TOKEN = os.getenv("GEMINI_API_TOKEN")
        if not self.GEMINI_API_TOKEN:
            raise ValueError("GEMINI_API_TOKEN environment variable required")

        genai.configure(api_key=self.GEMINI_API_TOKEN)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')

        self.system_prompt = self._create_system_prompt()

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
        if not page_html.strip():
            return []

        # Remove member tags containing logged in user info
        soup = BeautifulSoup(page_html, "html.parser")
        for tag in soup.find_all("div", class_="member"):
            tag.clear()

        # Convert to markdown
        page_md = markdownify(str(soup))

        # Split into individual activities
        content_list = page_md.split("* ## Feed post number")
        activities = []

        for i, content in enumerate(content_list):
            if i == 0:  # Skip header
                continue

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

        return activities

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

            # Extract publish date
            publish_date = await self._extract_date(activity.content_md)
            if not publish_date:
                content.processing_status = ContentDetails.ProcessingStatus.FAILED_MISSING_PUBLISH_DATE
                return content

            content.publish_date = publish_date
            content.publish_date_readable_str = publish_date.strftime("%d %B, %Y")

            # Check if content is stale
            cutoff_date = datetime.utcnow() - relativedelta(months=15)
            if publish_date < cutoff_date:
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
            response = await self._analyze_content(activity.content_md)
            if not response:
                return None

            content.detailed_summary = response.get("detailed_summary")
            content.concise_summary = response.get("concise_summary")
            content.one_line_summary = response.get("one_line_summary")

            content.category = response.get("category")
            content.category_reason = response.get("category_reason")

            content.focus_on_company = response.get("focus_on_company", False)
            content.focus_on_company_reason = response.get("focus_on_company_reason")

            # Extract people and products
            if content.focus_on_company:
                people_products = await self._extract_people_and_products(activity.content_md)
                content.main_colleague = people_products.get("main_colleague")
                content.main_colleague_reason = people_products.get("colleague_reason")
                content.product_associations = people_products.get("products", [])

            # Extract engagement metrics and metadata
            metadata = await self._extract_metadata(activity.content_md)
            content.author = metadata.get("author")
            content.author_type = metadata.get("author_type")
            content.author_linkedin_url = metadata.get("author_linkedin_url")
            content.hashtags = metadata.get("hashtags", [])
            content.num_linkedin_reactions = metadata.get("reactions")
            content.num_linkedin_comments = metadata.get("comments")
            content.num_linkedin_reposts = metadata.get("reposts")

            content.processing_status = ContentDetails.ProcessingStatus.COMPLETE
            content.openai_tokens_used = tokens_used

            return content

        except Exception as e:
            logger.error(f"Error parsing activity: {str(e)}", exc_info=True)
            return None

    async def _analyze_content(self, content_md: str) -> Dict[str, Any]:
        """Analyze content using Gemini."""
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
{
    "detailed_summary": string,
    "concise_summary": string,
    "one_line_summary": string,
    "category": string (one of: personal_thoughts, industry_update, company_news, product_update, social_update, other),
    "category_reason": string,
    "focus_on_company": boolean,
    "focus_on_company_reason": string,
    "products": [string]
}"""

            response = self.model.generate_content(prompt)
            if not response or not response.parts:
                return {}

            try:
                # Extract JSON from response
                return self._parse_json_response(response.parts[0].text)
            except Exception as e:
                logger.error(f"Error parsing response: {str(e)}")
                return {}

        except Exception as e:
            logger.error(f"Error analyzing content: {str(e)}", exc_info=True)
            return {}

    async def _extract_people_and_products(self, content_md: str) -> Dict[str, Any]:
        """Extract mentioned people and products."""
        try:
            prompt = f"""Analyze the following LinkedIn activity for people and products:

{content_md}

1. Identify the main colleague from {self.company_name} mentioned or discussed
2. List any products from {self.company_name} mentioned

Return as JSON:
{
            "main_colleague": string or null,
    "colleague_reason": string,
    "products": [string]
}"""

            response = self.model.generate_content(prompt)
            if not response or not response.parts:
                return {}

            return self._parse_json_response(response.parts[0].text)

        except Exception as e:
            logger.error(f"Error extracting people and products: {str(e)}", exc_info=True)
            return {}

    async def _extract_metadata(self, content_md: str) -> Dict[str, Any]:
        """Extract post metadata like author, hashtags, metrics."""
        try:
            prompt = f"""Extract metadata from this LinkedIn activity:

{content_md}

Return as JSON:
{
            "author": string,
    "author_type": "person" or "company",
    "author_linkedin_url": string,
    "hashtags": [string],
    "reactions": number or null,
    "comments": number or null,
    "reposts": number or null
}"""

            response = self.model.generate_content(prompt)
            if not response or not response.parts:
                return {}

            return self._parse_json_response(response.parts[0].text)

        except Exception as e:
            logger.error(f"Error extracting metadata: {str(e)}", exc_info=True)
            return {}

    async def _extract_date(self, content_md: str) -> Optional[datetime]:
        """Extract publish date from content."""
        try:
            prompt = f"""Extract the publish date from this LinkedIn activity:

{content_md}

Find date format like: 4h, 5d, 1mo, 2yr, 3w
Return just the date string, nothing else."""

            response = self.model.generate_content(prompt)
            if not response or not response.parts:
                return None

            date_str = response.parts[0].text.strip()
            return self._parse_relative_date(date_str)

        except Exception as e:
            logger.error(f"Error extracting date: {str(e)}", exc_info=True)
            return None

    def _parse_relative_date(self, date_str: str) -> Optional[datetime]:
        """Parse relative date string into datetime."""
        now = datetime.utcnow()

        # Match patterns like 4h, 5d, 1mo, 2yr, 3w
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
                return now - delta_func(value)

        return None

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from AI response with error handling."""
        try:
            # Clean response text
            text = response.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            import json
            return json.loads(text)

        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}
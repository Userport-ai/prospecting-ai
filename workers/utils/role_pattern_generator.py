import logging
from typing import Dict, Union, List

logger = logging.getLogger(__name__)

class RolePatternGenerator:
    """Generate standard regex patterns for role matching using AI service."""

    def __init__(self, ai_service):
        """Initialize with AI service."""
        self.ai_service = ai_service
        self.prompt_template = """
Generate a standard regex pattern that matches variations of these job titles, excluding the end_user, influencer roles.

Role Titles:
{titles}

Requirements:
- Pattern should use standard regex syntax
- Match common abbreviations (VP, Dir., Mgr., Sr., etc.)
- Match titles with different separators (spaces, hyphens, commas)
- Match titles with optional words (of, for, in)
- Match variations with department additions (e.g., "Sales" could be "Sales Operations" or "Sales Development")
- Match titles with geographic additions (Americas, EMEA, Global, etc.)
- Match when multiple departments are joined by "and" or "&"
- Handle existing abbreviations in input (e.g., "VP" or "Ops")
- Use non-capturing groups (?:) instead of capturing groups
- Also feel free to add some additional related buyer like roles

Return only the regex pattern as a JSON object with a single "pattern" field. No explanation or additional text.
Example: {{"pattern": "your-standard-regex-pattern-here"}}
"""

    async def generate_pattern(self, persona_roles: Dict[str, Union[List[str], str]]) -> str:
        """Generate regex pattern for role matching."""
        # Format titles, excluding end_users
        formatted_roles = {
            role_type: titles
            for role_type, titles in persona_roles.items()
            if role_type not in ['end_user', 'end_users', 'influencer', 'influencers']
        }

        # Format prompt
        prompt = self.prompt_template.format(
            titles=formatted_roles
        )

        try:
            # Get response from AI service
            response = await self.ai_service.generate_content(
                prompt=prompt,
                is_json=True,
                operation_tag="role_pattern_generation"
            )

            if not response or 'pattern' not in response:
                raise ValueError("Invalid response from AI service")

            return response['pattern']

        except Exception as e:
            logger.error(f"Error generating role pattern: {str(e)}")
            raise

# Example usage:
"""
async def main():
    ai_service = AIServiceFactory.create_service("gemini")
    generator = RolePatternGenerator(ai_service)
    
    persona_roles = {
        "buyers": [
            "Chief Revenue Officer",
            "VP of Sales",
            "Head of Sales Operations"
        ],
        "influencers": [
            "Sales Operations Manager",
            "Revenue Operations Director"
        ]
    }
    
    pattern = await generator.generate_pattern(persona_roles)
    print(f"Generated Regex pattern: {pattern}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
"""

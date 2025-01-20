import logging
from typing import Dict, Union, List

logger = logging.getLogger(__name__)

class RolePatternGenerator:
    """Generate standard regex patterns for role matching using AI service."""

    def __init__(self, ai_service):
        """Initialize with AI service."""
        self.ai_service = ai_service
        self.prompt_template = """
You are a super intelligent B2B Sales person who is tasked with figuring out the leads that will fall under the Buyer persona in a company.
You are given an initial list of Role titles that fall under the Buyer persona of the product you are trying to sell.

Initial Role titles list: {titles}

These Role titles are not exhaustive by any means and each prospective company has their own list of Role titles that may not match this initial list.
Using your intelligence and real world knowledge, suggest other Role titles using regular expressions, that fall under the same buyer persona but are also variants of the role titles in the initial list.
Variants can include:
1."&" instead of "and" and vice versa
2."VP" instead of "Vice President" and vice versa
3."GTM" instead of "CRO" and vice versa
4."Head of Enterprise Sales" instead of "Director of Sales" and vice versa
5."Head of Partnerships, EMEA" instead of "Head of Partnerships" and vice versa
6."Area Vice President, APAC Marketing" instead of "AVP Marketing" and vice versa
7."International Sales Head" instead of "CRO" and vice versa
8. Use regular expressions to do wider match, make stop words optional, etc.
9. Be exhaustive but total number of characters used across the array should not exceed 3000 characters. 

Here are 2 examples:
1.Initial Role titles list: [VP of Marketing, CMO] => [".*Vice President of Marketing, Senior VP (?:of)? Marketing.*", "Chief Marketing Officer", "Head of Marketing", "Director of Marketing", "VP Brand Partnerships", "North America VP of Marketing", "AVP Marketing - Central"]
2. Initial Role titles list: [ "Chief Revenue Officer", "VP of Sales", "Head of Sales Operations" ] => ["Chief\\s?Revenue\\s?Officer",
        "CRO", "Chief\\s?Commercial\\s?Officer", "CCO", "GTM\\s?Leader", "VP\\s?of\\s?Sales", "Vice\\s?President\\s?of\\s?Sales", "Senior\\s?VP\\s?of\\s?Sales", "SVP\\s?of\\s?Sales", "Senior\\s?Vice\\s?President\\s?of\\s?Sales", "VP\\s?Sales", "Vice\\s?President,\\s?Sales", "Sales\\s?VP", "Sales\\s?Vice\\s?President", "Global\\s?VP\\s?of\\s?Sales", "Global\\s?Vice\\s?President\\s?of\\s?Sales", "Regional\\s?VP\\s?of\\s?Sales", "Regional\\s?Vice\\s?President\\s?of\\s?Sales"]

Return as JSON:
{{
"role_titles": [string]
}}
"""

    async def generate_pattern(self, persona_roles: Dict[str, Union[List[str], str]]) -> str:
        """
        Generate a single regex pattern for role matching by combining multiple patterns.

        Args:
            persona_roles: Dictionary containing role types and their titles

        Returns:
            A single regex pattern string that matches any of the generated role patterns
        """
        # Format titles, excluding end_users and influencers
        formatted_roles = {
            role_type: titles
            for role_type, titles in persona_roles.items()
            if role_type not in ['end_user', 'end_users', 'influencer', 'influencers']
        }

        # Format prompt with the actual roles
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

            if not response or 'role_titles' not in response:
                logger.error(f"Invalid response format from AI service: {response}")
                raise ValueError("Invalid response from AI service: missing 'role_titles' key")

            # Join all patterns with | to create a single regex pattern
            combined_pattern = '|'.join(f"(?:{pattern})" for pattern in response['role_titles'])

            return combined_pattern

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
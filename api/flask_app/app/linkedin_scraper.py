import os
import re
import requests
from typing import Optional, Dict
from dotenv import load_dotenv
from utils import Utils
from models import LinkedInPost, PersonProfile

load_dotenv()


class LinkedInScraper:
    """Python wrapper around ProxyCurl and Piloterr APIs for scraping LinkedIn information for user, company and posts."""

    PILOTERR_API_KEY = os.getenv("PILOTERR_API_KEY")
    PILOTERR_POST_ENDPOINT = "https://piloterr.com/api/v2/linkedin/post/info"

    PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY")
    PROXYCURL_PROFILE_ENDPOINT = "https://nubela.co/proxycurl/api/v2/linkedin"

    @staticmethod
    def fetch_linkedin_post(post_url: str) -> LinkedInPost:
        """Fetches and returns LinkedIn post information for given URL.

        Piloterr API documentation: https://www.piloterr.com/library/linkedin-post-info.

        Args:
            post_url [string]: URL of the LinkedIn post.

        Returns:
            LinkedInPost object instance.
        """
        if not LinkedInScraper.is_valid_post(post_url):
            raise ValueError(f"Invalid LinkedIn post URL format: {post_url}")

        headers = LinkedInScraper._get_piloterr_request_headers()
        post_id: str = LinkedInScraper._get_post_id(post_url=post_url)
        params = LinkedInScraper._get_piloterr_query_params(query=post_id)
        try:
            response = requests.get(
                LinkedInScraper.PILOTERR_POST_ENDPOINT, headers=headers, params=params)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch LinkedIn post from Piloterr due to error: {e}")

        status_code = response.status_code
        if status_code != 200:
            raise ValueError(
                f"Got invalid status code: {status_code} when fetching LinkedIn post for url:  {post_url}")

        try:
            data = response.json()
        except Exception as e:
            raise ValueError(
                f"Failed to get JSON response when fetching LinkedIn post for url: {post_url}")

        post = LinkedInPost(**data)
        post.fetch_date = Utils.create_utc_time_now()
        return post

    def fetch_linkedin_profile(profile_url: str) -> Optional[PersonProfile]:
        """Fetches and returns LinkedIn Profile information of a given person from URL.

        Proxycurl API documentation: https://nubela.co/proxycurl/docs

        Piloterr also has an API but is inferiror to Proxycurl's APIs.
        """
        if not LinkedInScraper._is_valid_profile_url(profile_url):
            raise ValueError(
                f"Invalid URL format for LinkedIn profile: {profile_url}")

        headers = {
            'Authorization': f'Bearer {LinkedInScraper.PROXYCURL_API_KEY}'
        }
        params = {
            'linkedin_profile_url': profile_url,
            'skills': 'include',
            'use_cache': 'if-recent',
            'fallback_to_cache': 'on-error',
        }

        try:
            response = requests.get(
                LinkedInScraper.PROXYCURL_PROFILE_ENDPOINT, headers=headers, params=params)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch LinkedIn profile from Proxycurl: {e}")

        status_code = response.status_code
        if status_code != 200:
            if status_code == 404:
                # Profile not found, return None.
                return None

            raise ValueError(
                f"Got invalid status code: {status_code} when fetching LinkedIn Profile from Proxycurl for url:  {profile_url}")

        try:
            data = response.json()
        except Exception as e:
            raise ValueError(
                f"Failed to get JSON response when fetching LinkedIn Profile for url: {profile_url}")

        # Populate LinkedIn profile URL field in the response.
        person_profile = PersonProfile(**data)
        person_profile.linkedin_url = profile_url
        person_profile.date_synced = Utils.create_utc_time_now()
        return person_profile

    @staticmethod
    def _get_post_id(post_url: str) -> str:
        """Extracts Post ID from given LinkedIn Post URL."""
        match = re.search("activity-(\d+)-", post_url)

        if not match:
            raise ValueError(
                f"Could not find post ID in LinkedIn post URL: {post_url}")
        # Access the captured group and convert to integer
        return match.group(1)

    @staticmethod
    def is_valid_post(post_url: str) -> bool:
        """Returns true if valid linkedin post and false otherwise.

        Post url must be of this format: https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E
        """
        if "linkedin.com/posts" not in post_url or "activity-" not in post_url:
            return False
        return True

    @staticmethod
    def _is_valid_profile_url(profile_url: str) -> bool:
        """Returns true if valid Person profile URL format and false otherwise.

        Profile URL must be in this format: https://www.linkedin.com/in/srinivas-birasal/
        """
        return "linkedin.com/in/" in profile_url

    @staticmethod
    def _get_piloterr_query_params(query: str) -> Dict:
        """Returns standard params for given query string for Piloterr's APIs."""
        return {
            'query': query,
        }

    @staticmethod
    def _get_piloterr_request_headers() -> Dict:
        """Returns standard request headers for Piloterr APIs."""
        return {
            'Content-Type': 'application/json',
            'x-api-key': LinkedInScraper.PILOTERR_API_KEY
        }


if __name__ == "__main__":
    # import json
    # data = None
    # with open("../example_linkedin_info/proxycurl_profile_3.json", "r") as f:
    #     data = f.read()
    # profile_data = json.loads(data)
    # lprofile = PersonProfile(**profile_data)
    # print(lprofile)

    # post_url = 'https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E'
    # post_url = 'https://www.linkedin.com/posts/aniket-bajpai_forbes30under30-forbesunder30-growth-activity-7064856579463942144-RptV'
    # post_url = 'https://www.linkedin.com/posts/plaid-_were-with-plaids-ceo-zachary-perret-on-activity-7207003883506651136-gnif/?t=%7Bseek_to_second_number%7D'
    # post not found.
    # post_url = 'https://www.linkedin.com/posts/plaid-_there-is-still-a-chance-to-catch-up-on-everything-activity-7211762498528555009-vHps/'

    # post_url = 'https://www.linkedin.com/posts/a16z_on-this-episode-of-in-the-vault-plaid-ceo-activity-7212156930234941441-6bFX/'
    # post_url = "https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.linkedin.com/posts/jeandenisgreze_growth-engineering-program-reforge-activity-7183823123882946562-wyqe&ved=2ahUKEwiBxqillauHAxW3xDgGHWTvDbAQFnoECBMQAQ&usg=AOvVaw3Cp35kXvI-XKaRDuuU8RtS"
    # This one gave wrong result from Piloterr.
    # post_url = "https://www.linkedin.com/posts/jeandenisgreze_thrilled-to-announce-that-ownercom-raised-activity-7158717112633499650-ENK7/"
    # post_url = "https://www.linkedin.com/posts/zperret_credit-underwriting-in-the-us-is-broken-activity-7203797435322621953-v_Bn"
    # post_url = "https://www.linkedin.com/posts/jeandenisgreze_distributed-coroutines-a-new-primitive-soon-activity-7173787541630803969-ADdw"
    # post_url = "https://www.linkedin.com/posts/zperret_2024-fintech-predictions-with-zach-perret-activity-7155603572825427969-ThEB/"
    # post_url = "https://www.linkedin.com/posts/a2kapur_cloudbees-ceo-software-delivery-is-now-activity-6986004496485158912-vVyd?trk=public_profile_like_view"
    post_url = "https://www.linkedin.com/posts/a2kapur_security-is-the-new-healthcare-activity-7055957841920086016-Y6Hu"
    post_data = LinkedInScraper.fetch_linkedin_post(post_url)
    print(post_data)

    # profile_url = "https://www.linkedin.com/in/zperret/"
    # profile_url = "https://www.linkedin.com/in/srinivas-birasal/"
    # profile_url = "https://in.linkedin.com/in/aniket-bajpai"
    # LinkedInScraper.fetch_linkedin_profile(profile_url=profile_url)

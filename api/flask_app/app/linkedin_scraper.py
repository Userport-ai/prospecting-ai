import os
import re
import json
import requests
import urllib.parse
from enum import Enum
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Optional, Dict, List, Tuple
from utils import Utils
from langchain_core.documents import Document
from langchain_chroma import Chroma
from models import LinkedInPostOld, PersonProfile, CompanyProfile
from langchain_openai import OpenAIEmbeddings
# from pydantic import BaseModel, Field
# Can't use pydantic base model because cant embed this class in model class inherting from langchain base model.
from langchain_core.pydantic_v1 import BaseModel, Field
from dotenv import load_dotenv
load_dotenv()


class LinkedInPostDetails(BaseModel):
    class AuthorType(str, Enum):
        PERSON = "person"
        COMPANY = "company"

    author_name: Optional[str] = Field(
        default=None, description="Name of the author of the LinkedIn Post.")
    author_type: Optional[AuthorType] = Field(
        default=None, description="Type of author.")
    author_profile_url: Optional[str] = Field(
        default=None, description="LinkedIn profile URL of author. Can be person or company profile.")
    author_headline: Optional[str] = Field(
        default=None, description="Headline string associated with Author's profile. Only set for 'person' author type.")
    author_follower_count: Optional[str] = Field(
        default=None, description="Follower count string (not integer) of the author. Only set for 'company' author type.")
    publish_date: Optional[datetime] = Field(
        default=None, description="Date when this post was published.")
    url: Optional[str] = Field(
        default=None, description="URL of the LinkedIn Post. Only set for Post, for repost it is None.")
    text: str = Field(
        default="", description="Text associacted with the post. Set to empty when it is a pure repost.")
    text_links: List[Tuple[str, str]] = Field(
        default=[], description="List of tuples of links shared in the text of the post. Example: https://lnkd.in/eEyZQE-w (linkedin link) or even external links like https://cloudbees.io.")
    card_links: List[Tuple[str, str]] = Field(
        default=[], description="List of tuples of heading + URLs shared as part of the post's card section at the end.")
    num_reactions: Optional[int] = Field(
        default=None, description="Number of reactions on the post. Only set for Post, None for repost.")
    num_comments: Optional[int] = Field(
        default=None, description="Number of comments on the post.  Only set for Post, None for repost.")

    repost: Optional["LinkedInPostDetails"] = Field(
        default=None, description="Reference to the original post if this a repost else None.")


class LinkedInScraper:
    """Scrapes information from LinkedIn like user profile, company profile and posts and extracts content from it."""

    PILOTERR_API_KEY = os.getenv("PILOTERR_API_KEY")
    PILOTERR_POST_ENDPOINT = "https://piloterr.com/api/v2/linkedin/post/info"

    PROXYCURL_API_KEY = os.getenv("PROXYCURL_API_KEY")
    PROXYCURL_PERSON_PROFILE_ENDPOINT = "https://nubela.co/proxycurl/api/v2/linkedin"
    PROXYCURL_COMPANY_PROFILE_ENDPOINT = "https://nubela.co/proxycurl/api/linkedin/company"

    # Chroma DB path for saving data locally during development. Do not use in production.
    # Reference: https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/#basic-example-including-saving-to-disk.
    CHROMA_DB_PATH = "./chroma_db"

    OPERATION_TAG_NAME = "linkedin_post_scrape"

    # OpenAI configurations.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
    OPENAI_EMBEDDING_FUNCTION = OpenAIEmbeddings(
        model=OPENAI_EMBEDDING_MODEL, api_key=OPENAI_API_KEY)

    # Metadata Constant keys.
    URL = "url"
    POST = "post"
    DOCUMENTS = "documents"
    IDS = "ids"

    def __init__(self, url: str, dev_mode: bool = False) -> None:
        self.dev_mode = dev_mode
        self.url = url
        if dev_mode:
            self.db = Chroma(persist_directory=LinkedInScraper.CHROMA_DB_PATH,
                             embedding_function=LinkedInScraper.OPENAI_EMBEDDING_FUNCTION)
            self.index()

    def index(self):
        if not self.dev_mode:
            raise ValueError("Method should not be called in production.")

        post: Optional[LinkedInPostOld] = self.get_linkedin_post_from_db()
        if post:
            print("LinkedIn Post found in Db")
            self.post = post
        else:
            print("Fetching LinkedIn Post from API and writing it to db.")
            self.post = LinkedInScraper.fetch_linkedin_post(post_url=self.url)
            self.create_linkedin_post_in_db(post=self.post)

    @staticmethod
    def fetch_linkedin_post(post_url: str) -> LinkedInPostOld:
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

        return LinkedInPostOld(**data)

    @staticmethod
    def extract_post_details(post_body: str) -> LinkedInPostDetails:
        """Extracts and returns Post details from given Post Body Markdown formatted string."""
        post_lines: List[str] = LinkedInScraper.preprocess_post(
            post_body=post_body)

        class ParseState(Enum):
            NONE = 1
            POST_START_DETECTED = 2
            POST_AUTHOR_DETECTED = 3
            POST_HEADLINE_OR_FOLLOWERS_DETECTED = 4
            POST_PUBLISH_DATE_DETECTED = 5
            POST_URL_DETECTED = 6
            REPOST_START_DETECTED = 7
            REPOST_AUTHOR_DETECTED = 8
            REPOST_HEADLINE_OR_FOLLOWERS_DETECTED = 9
            REPOST_PUBLISH_DATE_DETECTED = 10
            REPOST_URL_DETECTED = 11
            POST_REACTIONS_AND_COMMENTS = 12

        post = LinkedInPostDetails()
        repost = None
        state: ParseState = ParseState.NONE
        # We choose between post and repost object.
        current_post_obj: LinkedInPostDetails = post
        for line in post_lines:
            if LinkedInScraper.is_like_button(line):
                # Done parsing post.
                break

            current_post_obj = post if repost is None else repost
            if state == ParseState.NONE:
                if LinkedInScraper.is_post_start(line):
                    post.author_type = LinkedInScraper.get_author_type(line)
                    state = ParseState.POST_START_DETECTED
            elif state == ParseState.POST_START_DETECTED:
                current_post_obj.author_name, current_post_obj.author_profile_url = LinkedInScraper.fetch_author_and_url(
                    line)
                state = ParseState.POST_AUTHOR_DETECTED
            elif state == ParseState.POST_AUTHOR_DETECTED:
                if current_post_obj.author_type == LinkedInPostDetails.AuthorType.PERSON:
                    current_post_obj.author_headline = line.strip()
                else:
                    current_post_obj.author_follower_count = line.strip()
                state = ParseState.POST_HEADLINE_OR_FOLLOWERS_DETECTED
            elif state == ParseState.POST_HEADLINE_OR_FOLLOWERS_DETECTED:
                publish_date = LinkedInScraper.fetch_publish_date(line)
                current_post_obj.publish_date = publish_date
                if not repost:
                    state = ParseState.POST_PUBLISH_DATE_DETECTED
                else:
                    # In a repost, we don't observe the original URL so jump directly to parsing text.
                    state = ParseState.POST_URL_DETECTED
            elif state == ParseState.POST_PUBLISH_DATE_DETECTED:
                url = LinkedInScraper.fetch_post_url(line)
                if url:
                    current_post_obj.url = url
                    state = ParseState.POST_URL_DETECTED
            elif state == ParseState.POST_URL_DETECTED:
                # If another post start is detected or reaction count is detected, change state.
                if LinkedInScraper.is_post_start(line):
                    # Start of repost.
                    repost = LinkedInPostDetails()
                    repost.author_type = LinkedInScraper.get_author_type(line)
                    state = ParseState.POST_START_DETECTED
                elif LinkedInScraper.fetch_num_reactions(line):
                    # Only post can have reactions, not repost.
                    post.num_reactions = LinkedInScraper.fetch_num_reactions(
                        line)
                    state = ParseState.POST_REACTIONS_AND_COMMENTS
                else:
                    card_link_tuple = LinkedInScraper.fetch_card_heading_and_url(
                        line)
                    if not card_link_tuple:
                        # Regular text. Extract links from line.
                        current_post_obj.text_links += LinkedInScraper.fetch_md_links(
                            line)
                        current_post_obj.text += "\n" + line
                    else:
                        # Add to card links list dictionary.
                        current_post_obj.card_links.append(card_link_tuple)
            elif state == ParseState.POST_REACTIONS_AND_COMMENTS:
                num_comments = LinkedInScraper.fetch_num_comments(line)
                if num_comments:
                    # Only post can have reactions, not repost.
                    post.num_comments = num_comments

            # Uncomment for debugging
            # print("--------")
            # print(line)

        if repost:
            post.repost = repost

        # Uncomment for debugging
        # print("\n\n\n")
        # import pprint
        # pprint.pprint(post.dict())
        return post

    @staticmethod
    def extract_post_details_v2(post_body: str) -> LinkedInPostDetails:
        """V2 version of Extracts and returns Post details from given Post Body Markdown formatted string."""
        post_lines: List[str] = LinkedInScraper.preprocess_post(
            post_body=post_body)

        class ParseState(Enum):
            NONE = 1
            POST_AUTHOR_DETECTED = 2
            POST_URL_DETECTED = 3
            POST_REACTIONS_AND_COMMENTS = 4

        post = LinkedInPostDetails()
        repost = None
        state: ParseState = ParseState.NONE
        # We choose between post and repost object.
        current_post_obj: LinkedInPostDetails = post
        for line in post_lines:
            if LinkedInScraper.is_like_button(line):
                # Done parsing post.
                break

            current_post_obj = post if repost is None else repost
            if state == ParseState.NONE:

                if LinkedInScraper.fetch_author_and_url(line):
                    # Found Author and URL, start of post.
                    # Set author name, profile URL and author type.
                    current_post_obj.author_name, current_post_obj.author_profile_url = LinkedInScraper.fetch_author_and_url(
                        line)
                    current_post_obj.author_type = LinkedInScraper.get_author_type_v2(
                        current_post_obj.author_profile_url)
                    state = ParseState.POST_AUTHOR_DETECTED
            elif state == ParseState.POST_AUTHOR_DETECTED:
                # Expect headline and publish date followed by post URL.
                line = line.strip()
                if LinkedInScraper.fetch_publish_date(line):
                    # Date when post or repost was published.
                    current_post_obj.publish_date = LinkedInScraper.fetch_publish_date(
                        line)
                    if repost:
                        # If this is repost, this is the final line before text begins, so update state.
                        state = ParseState.POST_URL_DETECTED
                elif LinkedInScraper.fetch_post_url(line):
                    # URL associated with post. Only for post, doesn't show for repost.
                    current_post_obj.url = LinkedInScraper.fetch_post_url(line)
                    state = ParseState.POST_URL_DETECTED
                else:
                    # Edited is a hardcoded line that can come up which is not the headline.
                    if line != 'Edited':
                        # This is headline or follower count.
                        if current_post_obj.author_type == LinkedInPostDetails.AuthorType.PERSON:
                            current_post_obj.author_headline = line
                        else:
                            current_post_obj.author_follower_count = line
            elif state == ParseState.POST_URL_DETECTED:
                if repost is None and LinkedInScraper.fetch_author_and_url(line):
                    # Start of repost.
                    # Set author name, profile URL and author type of repost.
                    repost = LinkedInPostDetails()
                    repost.author_name, repost.author_profile_url = LinkedInScraper.fetch_author_and_url(
                        line)
                    repost.author_type = LinkedInScraper.get_author_type_v2(
                        repost.author_profile_url)
                    state = ParseState.POST_AUTHOR_DETECTED

                elif LinkedInScraper.fetch_num_reactions(line):
                    # Only post can have reactions, not repost.
                    post.num_reactions = LinkedInScraper.fetch_num_reactions(
                        line)
                    state = ParseState.POST_REACTIONS_AND_COMMENTS

                else:
                    card_link_tuple = LinkedInScraper.fetch_card_heading_and_url(
                        line)
                    if not card_link_tuple:
                        # Regular text. Extract links from line.
                        current_post_obj.text_links += LinkedInScraper.fetch_md_links(
                            line)
                        current_post_obj.text += "\n" + line
                    else:
                        # Add to card links list dictionary.
                        current_post_obj.card_links.append(card_link_tuple)

            elif state == ParseState.POST_REACTIONS_AND_COMMENTS:
                if LinkedInScraper.fetch_num_comments(line):
                    # post can have comments.
                    post.num_comments = LinkedInScraper.fetch_num_comments(
                        line)

            # Uncomment for debugging
            # print("--------")
            # print(line)

        if repost:
            post.repost = repost

        # Uncomment for debugging
        # print("\n\n\n")
        # import pprint
        # pprint.pprint(post.dict())
        return post

    @staticmethod
    def is_post_start(line: str):
        """Detect if line is the start of a LinkedIn Post.
        Example line: "[![View profile for Anuj Kapur, graphic]()](https://www.linkedin.com/in/a2kapur?trk=public_post_feed-actor-image)"
        """
        pattern = r"\[!\[.*\]\(\)\]\(.*\)"
        return re.match(pattern, line) is not None

    @staticmethod
    def get_author_type(line: str) -> LinkedInPostDetails.AuthorType:
        if "profile" in line:
            return LinkedInPostDetails.AuthorType.PERSON

        if "organization" in line:
            return LinkedInPostDetails.AuthorType.COMPANY

        raise ValueError(f"Invalid authortype in line: {line}")

    @staticmethod
    def fetch_author_and_url(line: str) -> Tuple[str, str]:
        """Returns post author and url from given line.

        Example post: [Jean-Denis Greze](https://www.linkedin.com/in/jeandenisgreze?trk=public_post_feed-actor-name)
        Example repost: [Anuj Kapur](https://www.linkedin.com/in/a2kapur?trk=public_post_reshare_feed-actor-name)
        """
        # pattern = r"\[(.*)\]\((.*)\?trk=public_post_.*feed-actor-name\)"
        pattern = r"\[(.*)\]\((.*)\?trk=public_post_.*feed.*\)"
        match_result = re.match(pattern, line)
        if not match_result:
            return None
            # raise ValueError(
            #     f"Expected line: {line} to have post author and URL.")
        if "/in/" not in match_result[2] and "/company/" not in match_result[2]:
            return None
        if "graphic" in match_result[1]:
            # This is just the icon image, not the name of the author.
            return None
        return (match_result[1], match_result[2])

    @staticmethod
    def get_author_type_v2(author_profile_url: str) -> LinkedInPostDetails.AuthorType:
        """Returns if author is person or company from their profile URL."""
        if "/in/" in author_profile_url:
            return LinkedInPostDetails.AuthorType.PERSON

        elif "/company/" in author_profile_url:
            return LinkedInPostDetails.AuthorType.COMPANY

        raise ValueError(f"Invalid authortype in line: {author_profile_url}")

    @staticmethod
    def fetch_post_url(line: str) -> Optional[str]:
        """Returns URL of the LinkedIn post if found.

        Example: * [Report this post](/uas/login?session_redirect=https%3A%2F%2Fwww.linkedin.com%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_ellipsis-menu-semaphore-sign-in-redirect&guestReportContentType=POST&_f=guest-reporting).
        """
        pattern = r"\* \[Report this post\]\(.*session_redirect=(.*)\&trk=public_post.*\)"
        match_result = re.match(pattern, line)
        if not match_result:
            return None
        return urllib.parse.unquote(match_result[1])

    @staticmethod
    def fetch_publish_date(line: str) -> Optional[datetime]:
        """Returns datetime object of when post was published."""
        line = line.strip()
        week_pattern = r'(\d+)w'
        month_pattern = r'(\d+)mo'
        year_pattern = r'(\d+)y'

        week_result = re.match(week_pattern, line)
        month_result = re.match(month_pattern, line)
        year_result = re.match(year_pattern, line)
        if not week_result and not month_result and not year_result:
            return None

        time_now = Utils.create_utc_time_now()
        publish_date = None
        if week_result:
            # Subtract weeks.
            weeks = int(week_result[1])
            publish_date = time_now - relativedelta(weeks=weeks)
        elif month_result:
            # Subtract months.
            months = int(month_result[1])
            publish_date = time_now - relativedelta(months=months)
        else:
            # Subtract years.
            years = int(year_result[1])
            publish_date = time_now - relativedelta(years=years)

        return publish_date

    @staticmethod
    def fetch_card_heading_and_url(line: str) -> Optional[Tuple[str, str]]:
        """Returns Card Heading and URL if any in the post.

        Example: [![Distributed Coroutines: a new primitive soon in every developer’s toolkit]()## Distributed Coroutines: a new primitive soon in every developer’s toolkit### stealthrocket.tech](https://www.linkedin.com/redir/redirect?url=https%3A%2F%2Fstealthrocket%2Etech%2Fblog%2Fdistributed-coroutines%2F&urlhash=ALVW&trk=public_post_reshare_feed-article-content)
        """
        pattern = r"\[\!\[(.*)\]\(\).*\]\(.*redirect\?url=(.*)\&urlhash.*\)"
        match_result = re.match(pattern, line)
        if not match_result:
            return None
        return (match_result[1], urllib.parse.unquote(match_result[2]))

    @staticmethod
    def fetch_md_links(line: str) -> List[Tuple[str, str]]:
        """Returns all markdown links as a list of tuples in this line.

        Example: Join us at [https://cloudbees.io](https://cloudbees.io?trk=public_post-text) for many more [https://lnkd.in/gmC2q4J7](https://lnkd.in/gmC2q4J7?trk=public_post_reshare-text).
        """
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        all_md_links = []
        for match in re.findall(pattern, line):
            link_suffix_pattern = r"(.*)\?trk=public_post.*"
            res = re.match(link_suffix_pattern, match[1])
            if res:
                all_md_links.append((match[0], res[1]))
            else:
                all_md_links.append((match[0], match[1]))
        return all_md_links

    @staticmethod
    def fetch_num_reactions(line: str) -> Optional[int]:
        """Returns number of reactions in given line, if any.

        Example: [![]()![]()![]() 33](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_social-actions-reactions)
        """
        pattern = r"\[\!\[\].*\s* (\S*)\]\(.*\)"
        match_result = re.match(pattern, line)
        if not match_result:
            return None
        return int(match_result[1].replace(",", ""))

    @staticmethod
    def fetch_num_comments(line: str) -> Optional[int]:
        """Returns number of comments in given line, if any.

        Example: 3 Comments](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_social-actions-comments)
        """
        pattern = r"\[(.*) Comments]\(.*\&trk=public_post_social-actions-comments\)"
        match_result = re.match(pattern, line)
        if not match_result:
            return None
        return int(match_result[1])

    @staticmethod
    def is_like_button(line: str) -> bool:
        """Returns true if like button encountered else false.

        Example: Like](https://www.linkedin.com/signup/cold-join?session_redirect=https%3A%2F%2Fwww%2Elinkedin%2Ecom%2Fposts%2Frajsarkar_starting-2024-with-a-bang-g2-just-announced-activity-7160709081719033857-AkiZ&trk=public_post_comment_like)
        """
        pattern = r"\[Like]\(.*\&trk=public_post_comment_like\)"
        match_result = re.match(pattern, line)
        return True if match_result else False

    @staticmethod
    def preprocess_post(post_body: str) -> List[str]:
        """Splits post body into new lines, processed them and returns a list of lines."""
        post_lines: List[str] = []
        for line in post_body.split("\n"):
            stripped_line: str = line.strip()
            if stripped_line == "":
                # Nothing to do.
                continue
            post_lines.append(line)

        # Combine multiple lines that are have unbalanced brackets or parentheses into a single line.
        combined_lines: List[str] = []
        stack: List[str] = []
        current_combined_line: str = ""
        for line in post_lines:
            stack = LinkedInScraper.balance_brackets_and_parentheses(
                line=line, stack=stack)
            current_combined_line += line
            if len(stack) == 0:
                # Everything is balanced now.
                combined_lines.append(current_combined_line)
                current_combined_line = ""

        return combined_lines

    @staticmethod
    def balance_brackets_and_parentheses(line: str, stack: List[str]) -> List[str]:
        """Balances brackets and parenthes for given line and returns the updated stack."""
        for c in line:
            if c not in ['(', ')', '[', ']']:
                continue

            if len(stack) == 0:
                # You should not append closing brackets or parenthesis, they are likely not parathesis character then.
                # For example: :) is a smiley not a close of parenthesis. What a bug sigh.
                if c == '(' or c == '[':
                    stack.append(c)
                continue

            last_c = stack[-1]
            if (c == ')' and last_c == '(') or (c == ']' and last_c == '['):
                stack.pop()
                continue

            stack.append(c)
        return stack

    @staticmethod
    def fetch_person_profile(profile_url: str) -> Optional[PersonProfile]:
        """Fetches and returns LinkedIn Profile information of a given person from URL. Returns None if profile not found.

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
                LinkedInScraper.PROXYCURL_PERSON_PROFILE_ENDPOINT, headers=headers, params=params)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch Person profile from Proxycurl: {e}")

        status_code = response.status_code
        if status_code != 200:
            if status_code == 404:
                # Profile not found, return None.
                return None

            raise ValueError(
                f"Got invalid status code: {status_code} when fetching Person Profile from Proxycurl for url:  {profile_url}")

        try:
            data = response.json()
        except Exception as e:
            raise ValueError(
                f"Failed to get JSON response when fetching Person Profile for url: {profile_url}")

        # Populate LinkedIn profile URL field in the response.
        profile = PersonProfile(**data)
        profile.linkedin_url = profile_url
        return profile

    @staticmethod
    def fetch_company_profile(profile_url: str) -> Optional[PersonProfile]:
        """Fetches and returns LinkedIn Profile information of a given Company from URL. Returns None if company not found.

        Proxycurl API documentation: https://nubela.co/proxycurl/docs#company-api-company-profile-endpoint
        """
        if not LinkedInScraper.is_valid_company_url(url=profile_url):
            raise ValueError(
                f"Invalid URL format for LinkedIn company profile: {profile_url}")

        headers = {
            'Authorization': f'Bearer {LinkedInScraper.PROXYCURL_API_KEY}'
        }
        params = {
            'url': profile_url,
            'categories': 'include',
            'funding_data': 'include',
            'use_cache': 'if-recent',
            'fallback_to_cache': 'on-error',
        }

        response = None
        try:
            response = requests.get(
                LinkedInScraper.PROXYCURL_COMPANY_PROFILE_ENDPOINT, headers=headers, params=params)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch Company profile: {profile_url} from Proxycurl: {e}")

        status_code = response.status_code
        if status_code != 200:
            if status_code == 404:
                # Company Profile not found, return None.
                return None

            raise ValueError(
                f"Got invalid status code: {status_code} when fetching Company Profile from Proxycurl for url:  {profile_url}")

        data = None
        try:
            data = response.json()
        except Exception as e:
            raise ValueError(
                f"Failed to get JSON response when fetching Person Profile for url: {profile_url}")

        profile = CompanyProfile(**data)
        profile.linkedin_url = profile_url
        return profile

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
    def is_valid_company_url(url: str) -> bool:
        """Returns true if valid Company URL and false otherwise."""
        return "linkedin.com/company/" in url

    @staticmethod
    def is_valid_profile_or_company_url(url: str) -> bool:
        """Returns true if valid Profile or Company URL."""
        return "linkedin.com/in/" in url or "linkedin.com/company/" in url

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

    def create_linkedin_post_in_db(self, post_url: str, post: LinkedInPostOld):
        """Creates LinkedIn post in database for given URL."""
        post_json: str = post.model_dump_json()
        self.db.add_documents(documents=[Document(page_content=post_json, metadata={
                              LinkedInScraper.URL: post_url, LinkedInScraper.POST: True})])

    def get_linkedin_post_from_db(self, post_url: str) -> Optional[LinkedInPostOld]:
        post_docs: List[str] = self.db.get(where={
            "$and": [
                {LinkedInScraper.URL: post_url},
                {LinkedInScraper.POST: True}
            ]
        })[LinkedInScraper.DOCUMENTS]
        if len(post_docs) == 0:
            return None
        if len(post_docs) != 1:
            raise ValueError(
                f"Expected 1 doc for LinkedIn post URL: {post_url}, got: {post_docs}")
        post_json = post_docs[0]
        post_dict: Dict = json.loads(post_json)
        return LinkedInPostOld(**post_dict)

    def delete_linkedin_post_from_db(self):
        """Delete LinkedIn post from database."""
        post_ids: List[str] = self.db.get(where={
            "$and": [
                {LinkedInScraper.URL: self.url},
                {LinkedInScraper.POST: True}
            ]
        })[LinkedInScraper.IDS]
        self.db.delete(ids=post_ids)
        print(f"Deleted {len(post_ids)} LinkedIn posts from db.")


if __name__ == "__main__":
    # import json
    # data = None
    # with open("../example_linkedin_info/proxycurl_company_profile_1.json", "r") as f:
    #     data = f.read()
    # profile_data = json.loads(data)
    # lprofile = PersonProfile(**profile_data)
    # print(lprofile)
    # cprofile = CompanyProfile(**profile_data)
    # print(cprofile)

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
    # post_url = "https://www.linkedin.com/posts/a2kapur_security-is-the-new-healthcare-activity-7055957841920086016-Y6Hu"
    # post_data = LinkedInScraper.fetch_linkedin_post(post_url)
    # print(post_data)

    # profile_url = "https://www.linkedin.com/in/zperret/"
    # profile_url = "https://www.linkedin.com/in/srinivas-birasal/"
    # profile_url = "https://in.linkedin.com/in/aniket-bajpai"
    # LinkedInScraper.fetch_linkedin_profile(profile_url=profile_url)

    # profile_url = "https://www.linkedin.com/company/plaid-"
    profile_url = "https://www.linkedin.com/company/stripe/"
    LinkedInScraper.fetch_company_profile(profile_url=profile_url)

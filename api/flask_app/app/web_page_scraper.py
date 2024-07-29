import os
import random
import requests
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Optional, Tuple
from markdownify import markdownify
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import get_openai_callback
from utils import Utils
from models import ContentTypeEnum, ContentCategoryEnum, OpenAITokenUsage
from linkedin_scraper import LinkedInScraper, LinkedInPostDetails

from dotenv import load_dotenv
load_dotenv()


class OpenAIUsage(BaseModel):
    """Token usage when calling workflows using Open AI models."""
    url: str = Field(...,
                     description="URL for which tokens are being tracked.")
    operation_tag: str = Field(
        ..., description="Tag describing the operation for which cost is computed.")
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_in_usd: float = Field(...,
                                     description="Total cost of tokens used.")

    def convert_to_model(self) -> OpenAITokenUsage:
        """Converts to Token usage as defined by different pydantic model."""
        return OpenAITokenUsage(
            url=self.url, operation_tag=self.operation_tag, prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens, total_tokens=self.total_tokens, total_cost_in_usd=self.total_cost_in_usd
        )


class PageStructure(BaseModel):
    """Container to store page structure into header, body and footer."""
    header: Optional[str] = Field(
        default=None, description="Header of the page in Markdown formatted text. None if no header exists.")
    body: Optional[str] = Field(
        default=None, description="Body of the page in Markdown formatted text.")
    footer: Optional[str] = Field(
        default=None, description="Footer of the page in Markdown formatted text. None if it does not exist.")
    body_chunks: Optional[List[Document]] = Field(
        default=None, description="List of markdown formatted chunks that the page body is divided into. Set to None for LinkedIn post web pages only.")

    def to_str(self) -> str:
        """Returns string representation of page structure."""
        str_repr = ""
        if self.header:
            str_repr += f"Header\n=================\n{self.header}\n"
        str_repr += f"Body\n=================\n{self.body}\n"
        if self.footer:
            str_repr += f"Footer\n=================\n{self.footer}\n"
        return str_repr

    def to_doc(self) -> Document:
        """Returns document from page structure.."""
        page_content: str = ""
        if self.header:
            page_content += self.header
        page_content += self.body
        if self.footer:
            page_content += self.footer
        return Document(page_content=page_content)

    def get_size_mb(self) -> float:
        """Returns size of given page in megabytes."""
        page_content: str = self.to_doc().page_content
        return len(page_content.encode("utf-8"))/(1024.0 * 1024.0)


class PageContentInfo(BaseModel):
    """Container to return content information extracted from given web page."""
    url: Optional[str] = Field(default=None, description="URL of the page.")
    page_structure: Optional[PageStructure] = Field(
        default=None, description="Stores page structure.")
    linkedin_post_details: Optional[LinkedInPostDetails] = Field(
        default=None, description="Linkedin post details, set to None for other web pages.")

    type: Optional[ContentTypeEnum] = Field(
        default=None, description="Type of content (Interview, podcast, blog, article, LinkedIn post etc.).")
    type_reason: Optional[str] = Field(
        default=None, description="Reason for chosen enum value of type.")
    author: Optional[str] = Field(
        default=None, description="Full name of author of content if any.")
    publish_date: Optional[datetime] = Field(
        default=None, description="Date when this content was published in UTC timezone.")
    detailed_summary: Optional[str] = Field(default=None,
                                            description="A detailed summary of the content.")
    concise_summary: Optional[str] = Field(default=None,
                                           description="A concise summary of the content.")
    key_persons: Optional[List[str]] = Field(
        default=None, description="Names of key persons extracted from the content.")
    key_organizations: Optional[List[str]] = Field(
        default=None, description="Names of key organizations extracted from the content.")
    category: Optional[ContentCategoryEnum] = Field(
        default=None, description="Category of the content found")
    category_reason: Optional[str] = Field(
        default=None, description="Reason for chosen enum value of category.")
    num_linkedin_reactions: Optional[int] = Field(
        default=None, description="Number of LinkedIn reactions for a post. Set only for LinkedIn post web page and None otherwise.")
    num_linkedin_comments: Optional[int] = Field(
        default=None, description="Number of LinkedIn comments for a post. Set only for LinkedIn post web page and None otherwise.")

    openai_usage: Optional[OpenAIUsage] = Field(
        default=None, description="Total Open AI tokens used in fetching this content info.")


class PageFooterResult(BaseModel):
    """Detect footer start string within a web page."""
    footer_first_sentence: Optional[str] = Field(
        default=None, description="First sentence from where the footer starts.")
    reason: str = Field(...,
                        description="Reason for why this was chosen as footer start point.")


class ContentConciseSummary(BaseModel):
    """Class to parse content summary from page while parsing it top to bottom.

    This is strictly used only for LLM output parsing. The final summary should be read from ContentFinalSummary below.
    """
    concise_summary: str = Field(...,
                                 description="Concise Summary of the new passage text.")
    key_persons: List[str] = Field(
        default=[], description="Extract names of key persons from the new passage text. Set to empty if none found.")
    key_organizations: List[str] = Field(
        default=[], description="Extract names of key organizations from the new passage text. Set to empty if none found.")


class PostSummary(BaseModel):
    """Class to compute summary of a LinkedIn post.

    This is strictly used only for LLM output parsing. The final summary should be read from ContentFinalSummary below.
    """
    detailed_summary: str = Field(...,
                                  description="Detailed Summary of the text.")
    key_persons: List[str] = Field(
        default=[], description="Extract names of key persons from the text. Set to empty if none found.")
    key_organizations: List[str] = Field(
        default=[], description="Extract names of key organizations from the text. Set to empty if none found.")


class ContentFinalSummary(BaseModel):
    """Final summary and key persons information extracted from page content. Do not use for LLM structured output extraction."""
    detailed_summary: str = Field(...,
                                  description="Detailed Summary of the page content.")
    concise_summary: str = Field(...,
                                 description="Concise Summary of the page content.")
    key_persons: List[str] = Field(
        default=[], description="Key persons extracted from page content.")
    key_organizations: List[str] = Field(
        default=[], description="Key organizations extracted from page content.")


class ContentAuthorAndPublishDate(BaseModel):
    """Content author and publish date."""
    author: Optional[str] = Field(
        default=None, description="Full name of author of text. If not found, set to None.")
    publish_date: Optional[str] = Field(
        default=None, description="Date when this text was written. If not found, set to None.")


class ContentDate(BaseModel):
    """Used to parse date components."""
    day: Optional[int] = Field(
        default=None, description="Day of the parsed date. If not found, set to None.")
    month: Optional[int] = Field(
        default=None, description="Month of the parsed date. If not found, set to None.")
    year: Optional[int] = Field(
        default=None, description="Year of the parsed date. If not found, set to None.")


class ContentType(BaseModel):
    """Type of content (Interview, podcast, blog, article etc.) found on the web page."""
    enum_value: Optional[ContentTypeEnum] = Field(
        default=None, description="Enum value of the type that the text falls under. Set to None if it does not fall under any of the types defined.")
    reason: Optional[str] = Field(
        ..., description="Reason for enum value selection.")


class ContentCategory(BaseModel):
    """Category of the content."""
    enum_value: Optional[ContentCategoryEnum] = Field(
        default=None, description="Enum value of the category the text falls under. Set to None if it does not fall under any of the categories defined.")
    reason: Optional[str] = Field(...,
                                  description="Reason for enum value selection.")


class WebPageScraper:
    """
    Scrapes web page and extracts content from it.

    Set dev_mode to True only when using in development for testing.
    """

    # Open AI configurations.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
    OPENAI_EMBEDDING_FUNCTION = OpenAIEmbeddings(
        model=OPENAI_EMBEDDING_MODEL, api_key=OPENAI_API_KEY)
    OPENAI_GPT_4O_MINI_MODEL = os.getenv("OPENAI_GPT_4O_MINI_MODEL")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")

    # Chroma DB path for saving indices locally during development. Do not use in production.
    # Reference: https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/#basic-example-including-saving-to-disk.
    CHROMA_DB_PATH = "./chroma_db"

    OPERATION_TAG_NAME = "web_page_scrape"

    # Metadata Constant keys.
    URL = "url"
    DOCUMENTS = "documents"
    PAGE_HEADER = "page_header"
    PAGE_BODY = "page_body"
    PAGE_FOOTER = "page_footer"
    CHUNK_SIZE = "chunk_size"
    START_INDEX = "start_index"
    SPLIT_INDEX = "split_index"
    SUMMARY = "summary"

    def __init__(self,  url: str,  chunk_size: int = 4096, chunk_overlap: int = 200, dev_mode: bool = False) -> None:
        self.url = url
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.dev_mode = dev_mode

        if dev_mode:
            self.db = Chroma(persist_directory=WebPageScraper.CHROMA_DB_PATH,
                             embedding_function=WebPageScraper.OPENAI_EMBEDDING_FUNCTION)
            self.index()

    def index(self):
        """Workflow to fetch HTML page, split into page structure, create chunks and then store embeddings in vector database.

        Should only called be called in dev mode.
        """
        if not self.dev_mode:
            raise ValueError("Cannot call this method when not in dev mode")

        page_structure: Optional[PageStructure] = self.get_page_structure_from_db(
        )
        if page_structure:
            print("Fetched page structure from database.")
            print(f"Got {len(page_structure.body_chunks)} chunks in page.")
            self.page_structure: PageStructure = page_structure
        else:
            print("Page structure not found in database, fetching it from web.")
            doc = WebPageScraper.fetch_page(url=self.url)
            if self.is_valid_linkedin_post(url=self.url):
                page_structure = self.get_linkedin_post_structure(doc=doc)
            else:
                page_structure = self.get_page_structure(doc=doc)
            self.page_structure = self.create_page_structure_in_db(
                page_structure=page_structure)

    def fetch_page_content_info(self, company_name: str, person_name: str) -> PageContentInfo:
        """Scrapes web page and returns content from it for given company and person names."""
        if self.dev_mode:
            raise ValueError("Cannot fetch content in dev mode")

        doc = WebPageScraper.fetch_page(url=self.url)
        if self.is_valid_linkedin_post(url=self.url):
            return self.fetch_content_info_from_linkedin_post(company_name=company_name, person_name=person_name, doc=doc)

        return self.fetch_content_info_from_general_page(company_name=company_name, person_name=person_name, doc=doc)

    def fetch_content_info_from_general_page(self, company_name: str, person_name: str, doc: Document) -> PageContentInfo:
        """Fetches content information from General web page (not a LinkedIn post)."""
        print(f"Fetching content from general page: {self.url}")
        with get_openai_callback() as cb:
            page_structure: PageStructure = self.get_page_structure(
                doc=doc)

            final_summary: ContentFinalSummary = self.fetch_content_final_summary(
                page_body_chunks=page_structure.body_chunks)

            author_and_publish_date: ContentAuthorAndPublishDate = self.fetch_author_and_date(
                page_structure=page_structure)

            publish_date: Optional[datetime] = self.convert_to_datetime(
                parsed_date=author_and_publish_date.publish_date)

            type: ContentType = self.fetch_content_type(
                page_body_chunks=page_structure.body_chunks)

            category: ContentCategory = self.fetch_content_category(
                company_name=company_name, person_name=person_name, detailed_summary=final_summary.detailed_summary)

            tokens_used = OpenAIUsage(url=self.url, operation_tag=WebPageScraper.OPERATION_TAG_NAME, prompt_tokens=cb.prompt_tokens,
                                      completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            print(f"\nTokens used: {tokens_used}")

            return PageContentInfo(
                url=self.url,
                page_structure=page_structure,
                linkedin_post_details=None,
                type=type.enum_value,
                type_reason=type.reason,
                author=author_and_publish_date.author,
                publish_date=publish_date,
                detailed_summary=final_summary.detailed_summary,
                concise_summary=final_summary.concise_summary,
                key_persons=final_summary.key_persons,
                key_organizations=final_summary.key_organizations,
                category=category.enum_value,
                category_reason=category.reason,
                num_linkedin_reactions=None,
                num_linkedin_comments=None,
                openai_usage=tokens_used
            )

    def fetch_content_info_from_linkedin_post(self, company_name: str, person_name: str, doc: Document) -> PageContentInfo:
        """Fetches content information from LinkedIn post web page."""
        print(f"Fetching content from LinkedIn post: {self.url}")
        with get_openai_callback() as cb:
            page_structure: PageStructure = self.get_linkedin_post_structure(
                doc=doc)
            post_details: LinkedInPostDetails = LinkedInScraper.extract_post_details(
                post_body=page_structure.body)

            final_summary: ContentFinalSummary = self.fetch_post_final_summary(
                post_details=post_details)
            category: ContentCategory = self.fetch_content_category(
                company_name=company_name, person_name=person_name, detailed_summary=final_summary.detailed_summary)

            tokens_used = OpenAIUsage(url=self.url, operation_tag=WebPageScraper.OPERATION_TAG_NAME, prompt_tokens=cb.prompt_tokens,
                                      completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            print(f"\nTokens used: {tokens_used}")

            return PageContentInfo(
                url=self.url,
                page_structure=page_structure,
                linkedin_post_details=post_details,
                type=ContentTypeEnum.LINKEDIN_POST,
                type_reason=None,
                author=post_details.author_name,
                publish_date=post_details.publish_date,
                detailed_summary=final_summary.detailed_summary,
                concise_summary=final_summary.concise_summary,
                key_persons=final_summary.key_persons,
                key_organizations=final_summary.key_organizations,
                category=category.enum_value,
                category_reason=category.reason,
                num_linkedin_reactions=post_details.num_reactions,
                num_linkedin_comments=post_details.num_comments,
                openai_usage=tokens_used
            )

    def fetch_post_final_summary(self, post_details: LinkedInPostDetails) -> ContentFinalSummary:
        """Fetches final summary of LinkedIn post."""
        if self.dev_mode:
            detailed_summary: Optional[str] = self.get_detailed_summary_from_db(
            )
            if detailed_summary:
                print("Found summary in database")
                print(f"\nSummary: {detailed_summary}\n")
                return ContentFinalSummary(detailed_summary=detailed_summary, concise_summary="", key_persons=[], key_organizations=[])

        # Do not change this prompt before testing, results may get worse.
        post_or_repost_str: str = "Type: post"
        if post_details.repost:
            post_or_repost_str = "Type: repost"

        def get_headline_or_follower_count_str(post_details: LinkedInPostDetails) -> str:
            headline_or_follower_count_str: str = ""
            if post_details.author_type == LinkedInPostDetails.AuthorType.PERSON:
                headline_or_follower_count_str = f"Author Headline: {post_details.author_headline}"
            else:
                headline_or_follower_count_str = f"Author Follower count: {post_details.author_follower_count}"
            return headline_or_follower_count_str

        post_template = (
            "The 'Text' section below contains details about a LinkedIn 'post' or 'repost'.\n"
            "A 'post' contains a single piece of content while a 'repost' contains content from the 'original post' as well.\n"
            "The Author of the 'post' or 'repost' can be a 'person' or a 'company'. Similarly, the 'original post' can have the author be a 'person' or 'company'.\n"
            "Summarize the entire 'Text' section and make sure to highlight key numbers, quotes, announcements, persons and organizations in the summary.\n"
            "\n"
            "Text\n"
            "---------\n"
            f"{post_or_repost_str}\n"
            "URL: {post_url}\n"
            f"Publish Date: {post_details.publish_date}\n"
            f"Author: {post_details.author_name}\n"
            f"Author Type: {post_details.author_type.value}\n"
            f"{get_headline_or_follower_count_str(post_details=post_details)}\n"
            f"Author Profile URL:  {post_details.author_profile_url}\n\n"
        )

        if len(post_details.text) > 0:
            post_template += f"Content: {post_details.text}\n"

        if len(post_details.card_links) > 0:
            post_template += "Learn more by clicking on the links below:\n"
        for clink in post_details.card_links:
            post_template += f"* [{clink[0]}]({clink[1]})\n"

        if post_details.repost:
            repost_details: LinkedInPostDetails = post_details.repost
            repost_template = (
                "\n-----------------------------\n"
                f"Type: original post\n"
                f"Publish Date: {repost_details.publish_date}\n"
                f"Author: {repost_details.author_name}\n"
                f"Author Type: {repost_details.author_type.value}\n"
                f"{get_headline_or_follower_count_str(post_details=repost_details)}\n"
                f"Author Profile URL:  {repost_details.author_profile_url}\n\n"
            )
            if len(repost_details.text) > 0:
                repost_template += f"Content: {repost_details.text}\n"

            if len(repost_details.card_links) > 0:
                repost_template += "Learn more by clicking on the links below:\n"
            for clink in repost_details.card_links:
                repost_template += f"* [{clink[0]}]({clink[1]})"

            # Add repost template to post template.
            post_template = post_template + repost_template

        llm = ChatOpenAI(temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(
            PostSummary)
        prompt = PromptTemplate.from_template(post_template)
        chain = prompt | llm
        result: PostSummary = chain.invoke({'post_url': post_details.url})

        print("\n\nPost Summary: ", result.detailed_summary, "\n")

        if self.dev_mode:
            # Write summary to database.
            self.create_detailed_summary_in_db(summary=result.detailed_summary)

        # Concise summary is always the same as detailed summary for LinkedIn posts.
        return ContentFinalSummary(detailed_summary=result.detailed_summary, concise_summary=result.detailed_summary, key_persons=result.key_persons, key_organizations=result.key_organizations)

    def fetch_content_final_summary(self, page_body_chunks: List[Document]) -> ContentFinalSummary:
        """Returns final summary of content from page body using an iterative algorithm."""
        if self.dev_mode:
            detailed_summary: Optional[str] = self.get_detailed_summary_from_db(
            )
            if detailed_summary:
                print("Found summary in database")
                print(f"\nSummary: {detailed_summary}\n")
                return ContentFinalSummary(detailed_summary=detailed_summary, concise_summary="", key_persons=[], key_organizations=[])

        # Do not change this prompt before testing, results may get worse.
        summary_prompt_template = (
            "You are a smart web page analyzer.\n"
            "The 'Summary so far' section below contains a summary of page so far and the 'New Passage' section contains the new information from the page.\n"
            "Write a concise summary of only the 'New Passage' section using the 'Summary so far' section as context.\n"
            "Make sure to highlight key numbers, quotes, announcements, persons and organizations in the summary.\n"
            "\n"
            "Summary so far:\n"
            "{summary_so_far}\n"
            "\n"
            "New Passage:\n"
            "{new_passage}\n"
        )
        llm = ChatOpenAI(temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(
            ContentConciseSummary)
        prompt = PromptTemplate.from_template(summary_prompt_template)
        detailed_summary: str = ""
        key_persons: List[str] = []
        key_organizations: List[str] = []
        result: ContentConciseSummary
        for i, chunk in enumerate(page_body_chunks):
            new_passage = chunk.page_content
            chain = prompt | llm
            result: ContentConciseSummary = chain.invoke(
                {"summary_so_far": detailed_summary, "new_passage": new_passage})
            print(f"\n\nIteration {i+1}")
            print("--------------")
            print(f"Summary of new passage: {result.concise_summary}")
            print("Key persons: ", result.key_persons)
            print("Key organizations: ", result.key_organizations)
            detailed_summary = f"{detailed_summary}\n\n{result.concise_summary}"
            key_persons += result.key_persons
            key_organizations += result.key_organizations

        print(f"\n\nsummary: {detailed_summary}\n")
        print(f"key persons: {key_persons}\n")
        print(f"key organizations: {key_organizations}\n")

        # Compute concise summary of the detailed summary.
        concise_summary: str = self.fetch_concise_summary(
            detailed_summary=detailed_summary)

        if self.dev_mode:
            # Write summary to database.
            self.create_detailed_summary_in_db(summary=detailed_summary)

        return ContentFinalSummary(detailed_summary=detailed_summary, concise_summary=concise_summary, key_persons=key_persons, key_organizations=key_organizations)

    def fetch_concise_summary(self, detailed_summary: str) -> str:
        """Returns concise summary from given detailed summary."""
        prompt_template = (
            "Create a concise summary of the text below.\n"
            "\n"
            "Text:\n"
            "{text}"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL)
        chain = prompt | llm

        return chain.invoke(detailed_summary).content

    def fetch_author_and_date(self, page_structure: PageStructure) -> ContentAuthorAndPublishDate:
        """Fetches content details like author and publish date from the web page."""
        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "You are a smart web page analyzer. A part of the text from a web page is given below.\n"
            "Determine [1] who wrote the text and [2] the date it was published.\n"
            "\n"
            "Web Page Text:\n"
            "{page_text}"
        )
        # We want to use latest GPT model because it is likely more accurate than older ones like 3.5 Turbo.
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL)
        prompt = PromptTemplate.from_template(prompt_template)

        # We will fetch author and publish date details from the page header + first page body chunk.
        # Usually web pages have this information at the top so this algorithm should work well in most cases.
        page_text = ""
        if page_structure.header:
            page_text += page_structure.header
        page_text += page_structure.body_chunks[0].page_content

        chain = prompt | llm
        result = chain.invoke({"page_text": page_text})

        # Now using the string response from LLM, parse it for author and date information.
        # For some reason, using structured output in the first LLM call doesn't work. We need to
        # route the text answer from the first call to extract the structured output.
        content_details = self.parse_llm_output(text=result.content)
        print("\ncontent details: ", content_details)
        return content_details

    def fetch_content_type(self, page_body_chunks: List[Document]) -> ContentType:
        """Fetches content type (podcast, interview, article, blog post etc.) using Page body."""
        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "Does the text from a web page below fall into one of the following types?\n"
            f"* Article. [Enum value: {ContentTypeEnum.ARTICLE.value}].\n"
            f"* Blog post. [Enum value: {ContentTypeEnum.BLOG_POST.value}].\n"
            f"* Announcement. [Enum value: {ContentTypeEnum.ANNOUCEMENT.value}].\n"
            f"* Interview. [Enum value: {ContentTypeEnum.INTERVIEW.value}].\n"
            f"* Podcast. [Enum value: {ContentTypeEnum.PODCAST.value}].\n"
            f"* Panel Discussion. [Enum value: {ContentTypeEnum.PANEL_DISCUSSION.value}].\n"
            "\n"
            "{content}"
        )
        # We will use 40 model directly on the entire body as one string. Example podcast transcript was 6K tokens and we have up to 128K.
        # TODO: Use better way to break entire text into compressed text while maintaing structure and use that as input instead.
        content: str = "".join(
            [doc.page_content for doc in page_body_chunks])
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(ContentType)
        prompt = PromptTemplate.from_template(prompt_template)
        chain = prompt | llm
        content = (
            f'Page URL: {self.url}\n'
            f'Page Text:\n'
            f'{content}'
        )
        result = chain.invoke(content)

        print(f"\nContent type:{result}")
        return result

    def fetch_content_category(self, company_name: str, person_name: str, detailed_summary: str) -> ContentCategory:
        """Returns the category of the content using company name, person name and detailed summary."""
        # TODO: Update method so that when person name is optional, then we can skip some questions in the prompt.

        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question.\n"
            "\n"
            "Question: {question}\n"
            "\n"
            "Context: {context}\n"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(ContentCategory)
        chain = prompt | llm

        # Be very careful making changes to this prompt, it may result in worse results.
        question = (
            "Does the text below fall into one of the following categories?\n",
            f"* Personal thoughts shared by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_THOUGHTS.value}]\n"
            f"* Advice shared by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_ADVICE.value}]\n"
            f"* Anecdote shared by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_ANECDOTE.value}]\n"
            f"* {person_name} got promoted in their job. [Enum value: {ContentCategoryEnum.PERSONAL_PROMOTION.value}]\n"
            f"* Recognition or award received by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_RECOGITION.value}]\n"
            f"* Job change announcement by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_JOB_CHANGE.value}]\n"
            f"* Event attended by {person_name}. [Enum value: {ContentCategoryEnum.PERSONAL_EVENT_ATTENDED.value}]\n"
            f"* Talk given by {person_name} at an event or gathering. [Enum value: {ContentCategoryEnum.PERSONAL_TALK_AT_EVENT.value}]\n"
            f"* Launch of {company_name}'s product. [Enum value: {ContentCategoryEnum.PRODUCT_LAUNCH.value}]\n"
            f"* Update to {company_name}'s product. [Enum value: {ContentCategoryEnum.PRODUCT_UPDATE.value}]\n"
            f"* Shutdown of {company_name}'s product. [Enum value: {ContentCategoryEnum.PRODUCT_SHUTDOWN.value}]\n"
            f"* Appointment of leadership hire at {company_name}. [Enum value: {ContentCategoryEnum.LEADERSHIP_HIRE.value}]\n"
            f"* Leadership change at {company_name}. [Enum value: {ContentCategoryEnum.LEADERSHIP_CHANGE.value}]\n"
            f"* Promotion of an employee at {company_name}. [Enum value: {ContentCategoryEnum.EMPLOYEE_PROMOTION.value}]\n"
            f"* Employee leaving {company_name}. [Enum value: {ContentCategoryEnum.EMPLOYEE_LEAVING.value}]\n"
            f"* Hiring announcement for {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_HIRING.value}]\n"
            f"* {company_name}'s Quarterly or Annual Financial results Announcement. [Enum value: {ContentCategoryEnum.FINANCIAL_RESULTS.value}]\n"
            f"* A Story about {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_STORY.value}]\n",
            f"* Trends associated with {company_name}'s industry. [Enum value: {ContentCategoryEnum.INDUSTRY_TRENDS.value}]\n"
            f"* Announcement of {company_name}'s recent partnership with another company. [Enum value: {ContentCategoryEnum.COMPANY_PARTNERSHIP.value}]\n"
            f"* A significant achievement by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_ACHIEVEMENT.value}]\n"
            f"* Funding announcement by {company_name}. [Enum value: {ContentCategoryEnum.FUNDING_ANNOUNCEMENT.value}]\n"
            f"* IPO announcement by {company_name}. [Enum value: {ContentCategoryEnum.IPO_ANNOUNCEMENT.value}]\n"
            f"* Recognition or award received by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_RECOGNITION.value}]\n"
            f"* {company_name}'s anniversary announcement. [Enum value: [Enum value: {ContentCategoryEnum.COMPANY_ANNIVERSARY.value}]\n"
            f"* An event, conference or trade show hosted or attended by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_EVENT_HOSTED_ATTENDED.value}]\n"
            f"* A webinar hosted by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_WEBINAR.value}]\n"
            f"* Layoffs announced by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_LAYOFFS.value}]\n"
            f"* A challenge facing {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_CHALLENGE.value}]\n"
            f"* A rebranding initiative by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_REBRAND.value}]\n"
            f"* New market expansion announcement by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_NEW_MARKET_EXPANSION.value}]\n"
            f"* New office or branch opening announcement by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_NEW_OFFICE.value}]\n"
            f"* Social responsibility announcement by {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_SOCIAL_RESPONSIBILITY.value}]\n"
            f"* Legal challenge affecting {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_LEGAL_CHALLENGE.value}]\n"
            f"* Regulation that affects or will affect {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_REGULATION.value}]\n"
            f"* Lawsuit settlement relating to {company_name}. [Enum value: {ContentCategoryEnum.COMPANY_LAWSUIT.value}]\n"
            f"* Internal event for {company_name} employees only. [Enum value: {ContentCategoryEnum.COMPANY_INTERNAL_EVENT.value}]\n"
            f"* Company offsite for {company_name} employees. [Enum value: {ContentCategoryEnum.COMPANY_OFFSITE.value}]\n"
        )
        result = chain.invoke(
            {"question": question, "context": detailed_summary})

        print(f"\nCategories result: {result}")
        return result

    def parse_llm_output(self, text: str) -> ContentAuthorAndPublishDate:
        """Helper to fetch content details in structured format from unstructured LLM output.

        Used to process LLM output into content details class.
        """
        prompt_template = (
            "Extract properties of provided function from the given text. If a property is not found, set it to None.\n"
            "\n"
            "Text:\n"
            "{text}"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(ContentAuthorAndPublishDate)
        chain = prompt | llm
        return chain.invoke(text)

    def convert_to_datetime(self, parsed_date: Optional[str]) -> datetime:
        """Converts given parsed date (from web page) to datetime object in UTC timezone."""
        if not parsed_date:
            return None

        prompt_template = (
            "Convert given string representing a date into its its components: [1] Day, [2] Month and [3].\n"
            "If any of those 3 components is not avaiable in the string, set that component to None."
            "\n"
            "Date:{parsed_date}"
            ""
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=0, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(ContentDate)
        chain = prompt | llm
        result: ContentDate = chain.invoke(parsed_date)

        # Default values.
        day: int = result.day if result.day else 1
        month: int = result.month if result.month else 1
        year: int = result.year if result.year else datetime.now().year
        return Utils.create_utc_datetime(day=day, month=month, year=year)

    @staticmethod
    def fetch_page(url: str) -> Document:
        """Fetches HTML page and returns it as a Langchain Document with Markdown text content."""
        try:
            response = requests.get(url=url)
        except Exception as e:
            raise ValueError(
                f"ScrapePageGraph: HTTP error when fetching url: {url}, details: {e}")

        if response.status_code != 200:
            raise ValueError(
                f"Got non 200 response when fetching: {url}, code: {response.status_code}, text: {response.text}")
        if "text/html" not in response.headers["Content-Type"]:
            raise ValueError(
                f"Invalid response content type: {response.headers}")

        # Heading style argument is passed in to ensure we get '#' formatted headings.
        md = markdownify(response.text, heading_style="ATX")
        return Document(page_content=md)

    def split_into_chunks(self, doc: Document) -> List[Document]:
        """Split document into chunks using character splitter of given maximum chunk size and overlap."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size, chunk_overlap=self.chunk_overlap, add_start_index=True
        )
        chunks = text_splitter.split_documents([doc])
        print(
            f"Created: {len(chunks)} chunks when splitting: {url} using chunk size: {self.chunk_size}")
        return chunks

    def get_page_structure(self, doc: Document) -> PageStructure:
        """Splits given web page document into header, body, footer and body chunk contents and returns it."""
        page_header, remaining_md_page = self.get_page_header(doc=doc)

        # Fetch page footer.
        opeani_temperature: float = 0
        page_footer: Optional[str] = None
        page_body: str = remaining_md_page
        # Try max 5 times to fetch footer.
        for _ in range(0, 5):
            footer_result = WebPageScraper.fetch_page_footer(
                page_without_header=remaining_md_page, openai_temperature=opeani_temperature)
            if footer_result.footer_first_sentence is None:
                # Use random value between 0 and 1 for new temperature and try again.
                opeani_temperature = random.random()
                continue

            index = remaining_md_page.find(footer_result.footer_first_sentence)
            if index == -1:
                # Use random value between 0 and 1 for new temperature and try again.
                opeani_temperature = random.random()
                continue

            page_footer = remaining_md_page[index:]
            page_body = remaining_md_page[:index]
            break

        # Split page body into chunks.
        body_chunks: List[Document] = self.split_into_chunks(
            doc=Document(page_content=page_body))
        return PageStructure(header=page_header, body=page_body, footer=page_footer, body_chunks=body_chunks)

    def get_linkedin_post_structure(self, doc: Document) -> PageStructure:
        """Splits web page representing a linkedin post into header, body and footer elements."""
        post_header, remaining_post = self.get_page_header(doc=doc)

        # Look for "## More Relevant Posts" for start of footer.
        footer_start: str = "## More Relevant Posts"
        footer_index: int = remaining_post.find(footer_start)
        if footer_index == -1:
            raise ValueError(
                f"Could not find footer start: {footer_start} in LinkedIn post: {remaining_post}")
        post_body = remaining_post[:footer_index]
        post_footer = remaining_post[footer_index:]

        # Unlike a regular web page, we can skip splitting the body into chunks since a LinkedIn post is usually small in size.
        return PageStructure(header=post_header, body=post_body, footer=post_footer)

    def get_page_header(self, doc: Document) -> Tuple[Optional[str], str]:
        """Splits given markdown page document into header and remaining page."""
        markdown_page = doc.page_content

        # Fetch page header.
        heading_line: Optional[str] = None
        for level in range(1, 7):
            heading_line: Optional[str] = Utils.get_first_heading_in_markdown(
                markdown_text=markdown_page, level=level)
            if heading_line:
                break

        if not heading_line:
            raise ValueError(
                f"Could not find Heading (1-7) in Markdown page: {markdown_page[:1000]}")

        page_header: Optional[str] = None
        remaining_md_page: str = markdown_page
        if heading_line:
            index = markdown_page.find(heading_line)
            if index == -1:
                raise ValueError(
                    f"Could not find heading line: {heading_line} in markdown page: {markdown_page[:1000]}")
            page_header = markdown_page[:index]
            remaining_md_page = markdown_page[index:]

        return (page_header, remaining_md_page)

    @staticmethod
    def fetch_page_footer(page_without_header: str, openai_temperature: float = 1.0) -> PageFooterResult:
        """Use LLM to fetch the footer in given page without header."""
        prompt_template = (
            "You are a smart web page analyzer. Given below is the final chunk of a parsed web page in Markdown format.\n"
            "Can you identify if the chunk can be split into: [1] text with main content and [2] footer text that does not contribute to the main content?\n"
            "If yes, return the first sentence from where this footer starts. If no, return None.\n"
            "\n"
            "Chunk:\n"
            "{chunk}"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=openai_temperature, model_name=WebPageScraper.OPENAI_GPT_4O_MODEL).with_structured_output(PageFooterResult)
        chain = prompt | llm

        try:
            # We assume that page without header can fit within the token size of GPT40 which is 128K tokens for most pages.
            return chain.invoke({"chunk": page_without_header})
        except Exception as e:
            raise ValueError(f"Error in fetching page footer: {e}")

    def get_retriever(self,  k: int = 5) -> VectorStoreRetriever:
        """Return retriever from given database for known URL."""
        # Reference: https://api.python.langchain.com/en/latest/vectorstores/langchain_community.vectorstores.chroma.Chroma.html#langchain_community.vectorstores.chroma.Chroma.as_retriever
        search_kwargs = {
            'k': k,
            'filter': {
                # Note: You can only filter by one Metadata param, so we will use URL.
                WebPageScraper.URL: self.url,
            }
        }
        return self.db.as_retriever(search_kwargs=search_kwargs)

    def retrieve_relevant_docs(self, user_query: str) -> List[Document]:
        """Retreive k most relevant docs for give query from Vector store."""
        try:
            retriever = self.get_retriever()
            return retriever.invoke(user_query)
        except Exception as e:
            raise ValueError(
                f"Failed to fetch relevant docs for user query: {user_query} for url: {self.url} with error: {e}")

    def create_page_structure_in_db(self, page_structure: PageStructure) -> PageStructure:
        """Creates page structure in database for given URL and returns it.

        Each string in the page structure cannot be larger than 8192 tokens per: https://platform.openai.com/docs/api-reference/embeddings/create.
        """
        header: Optional[str] = page_structure.header
        if header:
            self.db.add_documents(documents=[Document(page_content=header, metadata={
                                  WebPageScraper.URL: self.url, WebPageScraper.PAGE_HEADER: True})])

        body: str = page_structure.body
        self.db.add_documents(documents=[Document(page_content=body, metadata={
                              WebPageScraper.URL: self.url, WebPageScraper.PAGE_BODY: True})])

        footer: str = page_structure.footer
        if footer:
            self.db.add_documents(documents=[Document(page_content=footer, metadata={
                                  WebPageScraper.URL: self.url, WebPageScraper.PAGE_FOOTER: True})])

        if page_structure.body_chunks:
            # Add page body chunks in database.
            page_structure.body_chunks = self.create_page_body_chunks_in_db(
                chunks=page_structure.body_chunks)
        return page_structure

    def get_page_structure_from_db(self) -> Optional[PageStructure]:
        """Returns page structure from db for given URL. If not found, returns None."""
        header_result: Dict = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_HEADER: True}
            ]
        })
        body_result: Dict = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_BODY: True}
            ]
        })
        footer_result: Dict = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_FOOTER: True}
            ]
        })
        header_list: List[str] = header_result[WebPageScraper.DOCUMENTS]
        body_list: List[str] = body_result[WebPageScraper.DOCUMENTS]
        footer_list: List[str] = footer_result[WebPageScraper.DOCUMENTS]
        if len(header_list) == 0 and len(body_list) == 0 and len(footer_list) == 0:
            # Result not in db.
            return None
        if len(body_list) != 1:
            raise ValueError(
                f"Expected body for url {self.url} to return 1 result, got: {body_list}")
        if len(header_list) > 1:
            raise ValueError(
                f"Expected header list for url {self.url} to return 1 result, got: {header_list}")
        if len(footer_list) > 1:
            raise ValueError(
                f"Expected footer list for url {self.url} to return 1 result, got: {footer_list}")
        page_structure = PageStructure(body=body_list[0])
        if len(header_list) > 0:
            page_structure.header = header_list[0]
        if len(footer_list) > 0:
            page_structure.footer = footer_list[0]

        # Fetch page body chunks.
        page_structure.body_chunks = self.get_page_body_chunks_from_db()
        return page_structure

    def delete_page_structure_from_db(self):
        """Delete page structures from database."""
        header_ids: List[str] = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_HEADER: True}
            ]
        })['ids']
        body_ids: List[str] = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_BODY: True}
            ]
        })['ids']
        footer_ids: List[str] = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.PAGE_FOOTER: True}
            ]
        })['ids']
        page_body_chunk_ids: List[str] = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.SPLIT_INDEX: {"$gte": 0}},
            ]
        })['ids']
        ids_to_delete: List[str] = header_ids + \
            body_ids + footer_ids + page_body_chunk_ids
        self.db.delete(ids=ids_to_delete)
        print(f"Deleted {len(ids_to_delete)} page structure docs")

    def create_page_body_chunks_in_db(self, chunks: List[Document]) -> List[Document]:
        """Create embeddings for page body chunks and store into vector db.

        Returns chunks with metadata populated.
        """
        for i, chunk in enumerate(chunks):
            # Add URL and chunk size metadata to document.
            chunk.metadata[WebPageScraper.URL] = self.url
            chunk.metadata[WebPageScraper.CHUNK_SIZE] = self.chunk_size
            chunk.metadata[WebPageScraper.SPLIT_INDEX] = i

        self.db.add_documents(documents=chunks)
        return chunks

    def get_page_body_chunks_from_db(self) -> List[Document]:
        """Return Page body chunks sorted by index number from the database for given URL."""
        result: Dict = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.SPLIT_INDEX: {"$gte": 0}},
            ]
        })
        sorted_results = sorted(zip(result["metadatas"], result[WebPageScraper.DOCUMENTS]),
                                key=lambda m: m[0][WebPageScraper.SPLIT_INDEX])

        return [Document(page_content=result[1])
                for result in sorted_results]

    def create_detailed_summary_in_db(self, summary: str):
        """Creates detailed summary in the database."""
        self.db.add_documents(documents=[Document(
            page_content=summary, metadata={WebPageScraper.URL: self.url, WebPageScraper.SUMMARY: True})])

    def get_detailed_summary_from_db(self) -> Optional[str]:
        """Return summary for given URL from db and None if it doesn't exist yet."""
        detailed_summary_result: Dict = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.SUMMARY: True}
            ]
        })
        summary_content: List[str] = detailed_summary_result[WebPageScraper.DOCUMENTS]
        if len(summary_content) == 0:
            # Result not in db.
            return None
        if len(summary_content) != 1:
            raise ValueError(
                f"Expected 1 doc for summary result, got: {summary_content}")
        return summary_content[0]

    def delete_detailed_summary_from_db(self):
        """Deletes summary from the database."""
        summary_ids: List[str] = self.db.get(where={
            "$and": [
                {WebPageScraper.URL: self.url},
                {WebPageScraper.SUMMARY: True}
            ]
        })['ids']
        self.db.delete(ids=summary_ids)
        print(f"Deleted {len(summary_ids)} summaries docs")

    def get_all_doc_ids_from_db(self) -> List[str]:
        """Get Ids for all documents (header, footer, body, chunks, summmaries etc.) in the database associated with the given URL."""
        return self.db.get(
            where={WebPageScraper.URL: self.url})['ids']

    def get_all_docs_from_db(self) -> List[Document]:
        return self.db.get(where={WebPageScraper.URL: self.url})[WebPageScraper.DOCUMENTS]

    def delete_all_docs_from_db(self):
        """Delete all documents associated with given url."""
        ids_to_delete: List[str] = self.get_all_doc_ids_from_db()
        self.db.delete(ids=ids_to_delete)
        print(f"Deleted {len(ids_to_delete)} docs from db")

    @staticmethod
    def is_valid_linkedin_post(url: str) -> bool:
        """Returns true if valid linkedin post and false otherwise.

        Post url must be of this format: https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E
        """
        if "linkedin.com/posts" not in url or "activity-" not in url:
            return False
        return True


if __name__ == "__main__":
    # url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
    # Migrated to new struct below.
    # url = "https://plaid.com/blog/year-in-review-2023/"
    # url = "https://python.langchain.com/v0.2/docs/tutorials/classification/"
    # Migrated to new struct below.
    # url = "https://a16z.com/podcast/my-first-16-creating-a-supportive-builder-community-with-plaids-zach-perret/"
    # Migrated to new struct below.
    # url = "https://techcrunch.com/2023/09/19/plaids-zack-perret-on-visa-valuations-and-privacy/"
    # url = "https://lattice.com/library/plaids-zach-perret-on-building-a-people-first-organization"
    # url = "https://podcasts.apple.com/us/podcast/zach-perret-ceo-at-plaid/id1456434985?i=1000623440329"
    # Migrated to new struct below.
    # url = "https://plaid.com/blog/introducing-plaid-layer/"
    # Migrated to new struct below.
    # url = "https://plaid.com/team-update/"
    # TODO: This sort of link found on linkedin posts, needs to be scraped one more time.
    # url = "https://lnkd.in/g4VDfXUf"
    # Able to scrape linkedin pulse as well. Could be useful content in the future.
    # url = "https://www.linkedin.com/pulse/blurred-lines-leadership-anuj-kapur"
    # Migrated to new struct below.
    # url = "https://www.spkaa.com/blog/devops-world-2023-recap-and-the-best-highlights"
    # Migrated to new struct below.
    # url = "https://www.forbes.com/sites/adrianbridgwater/2022/08/10/cloudbees-ceo-making-honey-in-the-software-delivery-hive/"
    # url = "https://www.cloudbees.com/newsroom/cloudbees-appoints-raj-sarkar-as-chief-marketing-officer"
    # url = "https://www.linkedin.com/posts/rajsarkar_forrestertei-totaleconomicimpact-teistudy-activity-7181275932207271938-S2lc/"
    # url = "https://www.linkedin.com/posts/a2kapur_macro-activity-7150910641900244992-0B5E"
    # Pulse can be scraped the same way as any web page. See below. It should work well.
    # url = "https://www.linkedin.com/pulse/culture-eats-strategy-breakfast-raj-sarkar"
    # This is a repost below with no text or comments.
    # url = "https://www.linkedin.com/posts/jeandenisgreze_distributed-coroutines-a-new-primitive-soon-activity-7173787541630803969-ADdw"
    # This is a repost with text and comments.
    # url = "https://www.linkedin.com/posts/jeandenisgreze_growth-engineering-program-reforge-activity-7183823123882946562-wyqe"
    url = "https://www.linkedin.com/posts/rajsarkar_fourteen-years-ago-in-2010-i-joined-google-activity-7208830932089225216-re5L/"
    # url = "https://www.linkedin.com/posts/a2kapur_cloudbees-buys-releaseiq-devops-orchestration-activity-6980945693720944641-Ayzi/?utm_source=share&utm_medium=member_desktop"
    # 3 years old post.
    # url = "https://www.linkedin.com/posts/a2kapur_christian-klein-the-details-guy-who-has-activity-6728126001274068992-Accy/?utm_source=share&utm_medium=member_desktop"
    # url = "https://www.linkedin.com/posts/rajsarkar_trust-devsecops-activity-7160709081719033857-aB9k/?utm_source=share&utm_medium=member_desktop"
    # url = "https://www.linkedin.com/posts/plaid-_were-with-plaids-ceo-zachary-perret-on-activity-7207003883506651136-gnif"
    # G2 recognition for Cloudbees.
    # url = "https://lnkd.in/eEyZQE-w"

    # person_name = "Zachary Perret"
    # person_name = "Al Cook"
    # company_name = "Plaid"
    # person_name = "Anuj Kapur"
    person_name = "Raj Sarkar"
    company_name = "Cloudbees"
    graph = WebPageScraper(url=url, dev_mode=True)
    # post_details: LinkedInPostDetails = LinkedInScraper.extract_post_details(
    #     post_body=graph.page_structure.body)
    # graph.fetch_post_final_summary(post_details=post_details)
    doc = graph.page_structure.to_doc()
    graph.fetch_content_info_from_linkedin_post(
        company_name=company_name, person_name=person_name, doc=doc)
    # print("Size of page in MB: ", graph.page_structure.get_size_mb(), " MB")

    # file_path = "../example_linkedin_info/webpage_markdown.txt"
    # file_path = "../example_linkedin_info/scraped_linkedin_repost_body.txt"
    # file_path = "../example_linkedin_info/scraped_linkedin_post_body.txt"
    # with open(file_path, "w") as f:
    #     f.write(graph.page_structure.body)

    # print(graph.page_structure.body)
    # graph.delete_summary_from_db()
    # graph.delete_all_docs_from_db()

    # final_summary = graph.fetch_content_final_summary(
    #     page_body_chunks=graph.page_structure.body_chunks)
    # print("concise summary: ", graph.fetch_concise_summary(
    #     detailed_summary=final_summary.detailed_summary))
    # graph.fetch_content_type(page_body_chunks=graph.page_structure.body_chunks)
    # graph.fetch_content_category(
    #     company_name=company_name, person_name=person_name, detailed_summary=final_summary.detailed_summary)
    # print(graph.fetch_page_content_info(company_name=company_name, person_name=person_name))

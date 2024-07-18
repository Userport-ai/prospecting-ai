import os
import random
import requests
from langchain_core.prompts import PromptTemplate
from typing import List, Dict, Optional
from markdownify import markdownify
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_community.callbacks import get_openai_callback
from utils import Utils

from dotenv import load_dotenv
load_dotenv()


class PageStructure(BaseModel):
    """Container to store page structure into header, body and footer."""
    header: Optional[str] = Field(
        default=None, description="Header of the page, None if no header exists.")
    body: str = Field(..., description="Body of the page.")
    footer: Optional[str] = Field(
        default=None, description="Footer of the page, None if it does not exist.")

    def to_str(self) -> str:
        """Returns string representation of page structure."""
        str_repr = ""
        if self.header:
            str_repr += f"Header\n=================\n{self.header}\n"
        str_repr += f"Body\n=================\n{self.body}\n"
        if self.footer:
            str_repr += f"Footer\n=================\n{self.footer}\n"
        return str_repr

    def to_doc(self) -> str:
        """Returns document string."""
        doc: str = ""
        if self.header:
            doc += self.header
        doc += self.body
        if self.footer:
            doc += self.footer
        return doc


class PageFooterResult(BaseModel):
    """Detect footer start string within a web page."""
    footer_first_sentence: Optional[str] = Field(
        default=None, description="First sentence from where the footer starts.")
    reason: str = Field(...,
                        description="Reason for why this was chosen as footer start point.")


class ContentConciseSummary(BaseModel):
    """Class to parse content summary from page while parsing it top to bottom."""
    concise_summary: str = Field(...,
                                  description="Concise Summary of the new passage text.")
    key_persons: List[str] = Field(
        default=[], description="Extract names of key persons from the new passage text. Set to empty if none found.")
    key_organizations: List[str] = Field(
        default=[], description="Extract names of key organizations from the new passage text. Set to empty if none found.")


class ContentDetails(BaseModel):
    """Content author and publish date."""
    author: Optional[str] = Field(
        default=None, description="Full name of author of text. If not found, set to None.")
    publish_date: Optional[str] = Field(
        default=None, description="Date when this text was written. If not found, set to None.")


class ContentAboutCompanyOrText(BaseModel):
    """Whether content is about company or text."""
    is_integral_part_of_text: bool = Field(
        ..., description="Set to True if integral part of the text and False otherwise.")
    reason: str = Field(...,
                        description="Reason for why it is integral part of the text.")


class ContentCategory(BaseModel):
    """Category of the content."""
    enum_value: Optional[str] = Field(
        default=None, description="Enum value of the category the text falls under. Set to None if it does not fall under any of the categories defined.")
    reason: Optional[str] = Field(
        ..., description="Reason for enum value selection.")


class OpenAITokenTracker(BaseModel):
    """Token usage tracker when calling chains using Open AI models."""
    url: str = Field(...,
                     description="URL for which tokens are being tracked.")
    operation_tag: str = Field(
        ..., description="Tag describing the operation for which cost is computed.")
    prompt_tokens: int = Field(..., description="Prompt tokens used")
    completion_tokens: int = Field(..., description="Completion tokens used")
    total_tokens: int = Field(..., description="Total tokens used")
    total_cost_in_usd: float = Field(...,
                                     description="Total cost of tokens used.")


class ScrapePageGraph:
    """Uses Langchain to construct a graph that fetches HTML page and parses it into Markdown chunks.

    The class can then be queried multiple times for different answers by clients.
    """

    # Open AI configurations.
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_EMBEDDING_MODEL = "text-embedding-ada-002"
    OPENAI_EMBEDDING_FUNCTION = OpenAIEmbeddings(
        model=OPENAI_EMBEDDING_MODEL, api_key=OPENAI_API_KEY)
    OPENAI_GPT_3_5_TURBO_MODEL = os.getenv("OPENAI_GPT_3_5_TURBO_MODEL")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")

    # Chroma DB path for saving indices locally.
    # TODO: Make this path per client (worker) in production so they don't step on each other.
    # Reference: https://python.langchain.com/v0.2/docs/integrations/vectorstores/chroma/#basic-example-including-saving-to-disk.
    CHROMA_DB_PATH = "./chroma_db"

    OPERATION_TAG_NAME = "analyze_page_workflow"

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

    def __init__(self,  url: str, start_indexing: bool = False, chunk_size: int = 4096, chunk_overlap: int = 200) -> None:
        self.url = url
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.db = Chroma(persist_directory=ScrapePageGraph.CHROMA_DB_PATH,
                         embedding_function=ScrapePageGraph.OPENAI_EMBEDDING_FUNCTION)

        if start_indexing:
            self.index()

    def index(self):
        """Workflow to fetch HTML page, split into page structure, create chunks and then store embeddings in vector database."""
        page_structure = self.get_page_structure_from_db(
        )
        doc: Document = None
        if page_structure:
            print("Fetched page structure from database.")
            self.page_structure: PageStructure = page_structure
            doc = self.page_structure.to_doc()
        else:
            print("Page structure not found in database, fetching it from web.")
            doc = ScrapePageGraph.fetch_page(url=self.url)
            self.page_structure: PageStructure = ScrapePageGraph.get_page_structure(
                doc=doc)
            self.create_page_structure_in_db(
                page_structure=self.page_structure)

        page_body_chunks: List[Document] = self.get_page_body_chunks_from_db(
        )
        if len(page_body_chunks) > 0:
            print(
                f"Found {len(page_body_chunks)} page body chunks in database")
            self.page_body_chunks = page_body_chunks
        else:
            print("Page body chunks not found in database, creating it.")
            page_body_chunks = self.split_into_chunks(
                doc=Document(page_content=self.page_structure.body))
            self.page_body_chunks = self.create_page_body_chunks_in_db(
                chunks=page_body_chunks)

    def get_retriever(self,  k: int = 5) -> VectorStoreRetriever:
        """Return retriever from given database for known URL."""
        # Reference: https://api.python.langchain.com/en/latest/vectorstores/langchain_community.vectorstores.chroma.Chroma.html#langchain_community.vectorstores.chroma.Chroma.as_retriever
        search_kwargs = {
            'k': k,
            'filter': {
                # Note: You can only filter by one Metadata param, so we will use URL.
                ScrapePageGraph.URL: self.url,
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

    def analyze_page(self, person_name: str, company_name: str):
        """Runs analysis of the scraped web page."""
        with get_openai_callback() as cb:
            summary = self.fetch_content_summary()

            content_details = self.fetch_author_and_date()

            self.fetch_content_type(
                content_details=content_details, combined_summaries=summary)

            self.is_content_about_company_or_person(
                company_or_person_name=company_name, combined_summaries=summary)

            self.fetch_content_category(
                company_name=company_name, person_name=person_name, summary=summary)

            token_tracker = OpenAITokenTracker(url=self.url, operation_tag=ScrapePageGraph.OPERATION_TAG_NAME, prompt_tokens=cb.prompt_tokens,
                                               completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
            print(f"\nTokens used: {token_tracker}")

    def fetch_content_summary(self) -> str:
        """Returns content summary of a web page body using an iterative algorithm."""
        summary: Optional[str] = self.get_summary_from_db()
        if summary:
            print("Found summary in database")
            print(f"\nSummary: {summary}\n")
            return summary

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
        llm = ChatOpenAI(temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(
            ContentConciseSummary)
        prompt = PromptTemplate.from_template(summary_prompt_template)
        text_summary: str = ""
        key_persons: List[str] = []
        key_organizations: List[str] = []
        result: ContentConciseSummary
        for i, chunk in enumerate(self.page_body_chunks):
            new_passage = chunk.page_content
            chain = prompt | llm
            result: ContentConciseSummary = chain.invoke(
                {"summary_so_far": text_summary, "new_passage": new_passage})
            print(f"\n\nIteration {i+1}")
            print("--------------")
            print(f"Summary of new passage: {result.concise_summary}")
            print("Key persons: ", result.key_persons)
            print("Key organizations: ", result.key_organizations)
            text_summary = f"{text_summary}\n\n{result.concise_summary}"
            key_persons += result.key_persons
            key_organizations += result.key_organizations

        print(f"\n\nsummary: {text_summary}\n")
        print(f"key persons: {key_persons}\n")
        print(f"key organizations: {key_organizations}\n")

         # Write summary to database.
        self.create_summary_in_db(summary=text_summary)

        return text_summary

    def fetch_author_and_date(self) -> ContentDetails:
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
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL)
        prompt = PromptTemplate.from_template(prompt_template)

        # We will fetch author and publish date details from the page header + first page body chunk.
        # Usually web pages have this information at the top so this algorithm should work well in most cases.
        page_text = ""
        if self.page_structure.header:
            page_text += self.page_structure.header
        page_text += self.page_body_chunks[0].page_content

        chain = prompt | llm
        result = chain.invoke({"page_text": page_text})

        # Now using the string response from LLM, parse it for author and date information.
        # For some reason, using structured output in the first LLM call doesn't work. We need to
        # route the text answer from the first call to extract the structured output.
        content_details = self.parse_llm_output(text=result.content)
        print("\ncontent details: ", content_details)
        return content_details

    def fetch_content_type(self, content_details: ContentDetails, combined_summaries: str) -> str:
        """Fetches content type using given detials and combined summaries of text.

        Currenly returning LLM string output without parsing.
        """
        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "You are an assistant for question-answering tasks. Use the following pieces of retrieved content to answer the question.\n"
            "If you don't know the answer or it's not in the content, just say you don't know.\n"
            "\n"
            "Question: {question}\n"
            "\n"
            "## Content:\n"
            "{content}"
        )
        # We want to use latest GPT model because it is likely more accurate than older ones like 3.5 Turbo.
        llm = ChatOpenAI(
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL)
        prompt = PromptTemplate.from_template(prompt_template)

        chain = prompt | llm
        question = "What type of content does this text represent?"
        content = (
            f'URL: {self.url}\n'
            f'Author:{content_details.author}\n'
            f'Date published:{content_details.publish_date}\n'
            f'Detailed Summary: {combined_summaries}'
        )
        result = chain.invoke(
            {"question": question, "content": content})

        # Now using the string response from LLM, parse it for author and date information.
        # return self.parse_llm_output(content=result.content)
        print(f"\nContent type:{result}")
        # TODO: Parse content type and return enum. Right now it is just a sentence provided by LLM.
        return result.content

    def is_content_about_company_or_person(self, company_or_person_name: str, combined_summaries: str):
        """Tests if company name or person is an important part of the combined summaries content."""
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
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(ContentAboutCompanyOrText)
        chain = prompt | llm

        question = f"Is {company_or_person_name} an integral part of the text below?"
        result = chain.invoke(
            {"question": question, "context": combined_summaries})

        print(f"\n{result}")
        return result

    def fetch_content_category(self, company_name: str, person_name: str, summary: str) -> ContentCategory:
        """Returns the category of the content using company name, person name and combined summary."""
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
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(ContentCategory)
        chain = prompt | llm

        question = (
            "Does the text below fall into one of the following categories?\n",
            f"* Personal thoughts shared by {person_name}. [Enum value: personal_thoughts]\n"
            f"* Advice shared by {person_name}. [Enum value: personal_advice]\n"
            f"* Anecdote shared by {person_name}. [Enum value: personal_anecdote]\n"
            f"* Launch of {company_name}'s product. [Enum value: product_launch]\n"
            f"* Update to {company_name}'s product. [Enum value: product_update]\n"
            f"* Shutdown of {company_name}'s product. [Enum value: product_shutdown]\n"
            f"* Appointment of leadership hire at {company_name}. [Enum value: leader_hire]\n"
            f"* Promotion of an employee at {company_name}. [Enum value: employee_promotion]\n"
            f"* Employee leaving {company_name}. [Enum value: employee_leaving]\n"
            f"* Hiring announcement for {company_name}. [Enum value: company_hiring]\n"
            f"* Financial results announcement of {company_name}. [Enum value: financial_results]\n"
            f"* A Story about {company_name}. [Enum value: company_story]\n",
            f"* Trends associated with {company_name}'s industry. [Enum value: industry_trends]\n"
            f"* Announcement of {company_name}'s recent partnership with another company. [Enum value: company_partnership]\n"
            f"* A significant achievement by {company_name}. [Enum value: company_achievement]\n"
            f"* Funding announcement by {company_name}. [Enum value: funding_announcement]\n"
            f"* IPO announcement by {company_name}. [Enum value: ipo_announcement]\n"
            f"* Recognition or award received by {company_name}. [Enum value: company_recognition]\n"
            f"* {company_name}'s anniversary announcement. [Enum value: company_anniversary]\n"
            f"* Sales growth or user base growth milestone achieved by {company_name}. [Enum value: sales_user_growth_milestone]\n"
            f"* An event, conference or trade show hosted or attended by {company_name}. [Enum value: event_hosted_attended]\n"
            f"* A webinar hosted by {company_name}. [Enum value: company_webinar]\n"
            f"* Layoffs announced by {company_name}. [Enum value: company_layoffs]\n"
            f"* A challenge facing {company_name}. [Enum value: company_challenge]\n"
            f"* A rebranding initiative by {company_name}. [Enum value: company_rebrand]\n"
            f"* New market expansion announcement by {company_name}. [Enum value: company_new_market_expansion]\n"
            f"* New office or branch opening announcement by {company_name}. [Enum value: company_new_office]\n"
            f"* Social responsibility announcement by {company_name}. [Enum value: company_social_responsibility]\n"
            f"* Legal challenge affecting {company_name}. [Enum value: company_legal_challenge]\n"
            f"* Regulation relating to {company_name}. [Enum value: company_regulation]\n"
            f"* Lawsuit settlement relating to {company_name}. [Enum value: company_lawsuit]\n"
            f"* Internal event for {company_name} employees only. [Enum value: company_internal_event]\n"
            f"* Company offsite for {company_name} employees. [Enum value: company_offsite]\n"
        )
        result = chain.invoke(
            {"question": question, "context": summary})

        print(f"\nCategories result: {result}")
        return result

    def parse_llm_output(self, text: str) -> ContentDetails:
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
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(ContentDetails)
        chain = prompt | llm
        return chain.invoke(text)

    @staticmethod
    def format_docs(docs: List[Document]) -> str:
        """Helper since StuffDocumentsChain gives some validation error when structued output is
        specified with LLM model. So using this function as workaround to combines docs to text.
        """
        return "\n\n".join(doc.page_content for doc in docs)

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

    @staticmethod
    def get_page_structure(doc: Document) -> PageStructure:
        """Splits given web page document into header, body and footer contents and returns it."""
        markdown_page = doc.page_content

        # Fetch page header.
        heading_line: Optional[str] = None
        for level in range(1, 7):
            heading_line: Optional[str] = Utils.get_first_heading_in_markdown(
                markdown_text=markdown_page, level=level)
            if heading_line:
                break

        page_header: Optional[str] = None
        remaining_md_page: str = markdown_page
        if heading_line:
            index = markdown_page.find(heading_line)
            page_header = markdown_page[:index]
            remaining_md_page = markdown_page[index:]

        # Fetch page footer. Try 3 times max.
        opeani_temperature: float = 0
        page_footer: Optional[str] = None
        page_body: str = remaining_md_page
        # Try max 5 times to fetch footer.
        for _ in range(0, 5):
            footer_result = ScrapePageGraph.fetch_page_footer(
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

        return PageStructure(header=page_header, body=page_body, footer=page_footer)

    @staticmethod
    def fetch_page_footer(page_without_header: str, openai_temperature: float = 1.0) -> PageFooterResult:
        """Use LLM to fetch the footer in given page without header."""
        prompt_template = (
            "You are a smart web page analyzer. Given below is the final chunk of a parsed web page in Markdown format.\n"
            # "Can you identify if the chunk has a footer containing a bunch of links that are unrelated to the main content?\n"
            "Can you identify if the chunk can be split into: [1] text with main content and [2] footer text that does not contribute to the main content?\n"
            "If yes, return the first sentence from where this footer starts. If no, return None.\n"
            "\n"
            "Chunk:\n"
            "{chunk}"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=openai_temperature, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(PageFooterResult)
        chain = prompt | llm

        try:
            # We assume that page without header can fit within the token size of GPT40 which is 128K tokens for most pages.
            return chain.invoke({"chunk": page_without_header})
        except Exception as e:
            raise ValueError(f"Error in fetching page footer: {e}")

    def create_page_body_chunks_in_db(self, chunks: List[Document]) -> List[Document]:
        """Create embeddings for page body chunks and store into vector db.

        Returns chunks with metadata populated.
        """
        for i, chunk in enumerate(chunks):
            # Add URL and chunk size metadata to document.
            chunk.metadata[ScrapePageGraph.URL] = self.url
            chunk.metadata[ScrapePageGraph.CHUNK_SIZE] = self.chunk_size
            chunk.metadata[ScrapePageGraph.SPLIT_INDEX] = i

        self.db.add_documents(documents=chunks)
        return chunks

    def get_page_body_chunks_from_db(self) -> List[Document]:
        """Return Page body chunks sorted by index number from the database for given URL."""
        result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.SPLIT_INDEX: {"$gte": 0}},
            ]
        })
        sorted_results = sorted(zip(result["metadatas"], result[ScrapePageGraph.DOCUMENTS]),
                                key=lambda m: m[0][ScrapePageGraph.SPLIT_INDEX])

        return [Document(page_content=result[1])
                for result in sorted_results]

    def delete_page_body_chunks_from_db(self):
        """Delete page body chunks from database."""
        page_body_chunk_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.SPLIT_INDEX: {"$gte": 0}},
            ]
        })['ids']
        self.db.delete(ids=page_body_chunk_ids)
        print(f"Deleted {len(page_body_chunk_ids)} page body chunk docs")

    def create_page_structure_in_db(self, page_structure: PageStructure):
        """Creates page structure in database for given URL.

        Each string in the page structure cannot be larger than 8192 tokens per: https://platform.openai.com/docs/api-reference/embeddings/create.
        """
        header: Optional[str] = page_structure.header
        if header:
            self.db.add_documents(documents=[Document(page_content=header, metadata={
                                  ScrapePageGraph.URL: self.url, ScrapePageGraph.PAGE_HEADER: True})])

        body: str = page_structure.body
        self.db.add_documents(documents=[Document(page_content=body, metadata={
                              ScrapePageGraph.URL: self.url, ScrapePageGraph.PAGE_BODY: True})])

        footer: str = page_structure.footer
        if footer:
            self.db.add_documents(documents=[Document(page_content=footer, metadata={
                                  ScrapePageGraph.URL: self.url, ScrapePageGraph.PAGE_FOOTER: True})])

    def get_page_structure_from_db(self) -> Optional[PageStructure]:
        """Returns page structure from db for given URL. If not found, returns None."""
        header_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_HEADER: True}
            ]
        })
        body_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_BODY: True}
            ]
        })
        footer_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_FOOTER: True}
            ]
        })
        header_list: List[str] = header_result[ScrapePageGraph.DOCUMENTS]
        body_list: List[str] = body_result[ScrapePageGraph.DOCUMENTS]
        footer_list: List[str] = footer_result[ScrapePageGraph.DOCUMENTS]
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
        return page_structure

    def delete_page_structure_from_db(self):
        """Delete page structures from database."""
        header_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_HEADER: True}
            ]
        })['ids']
        body_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_BODY: True}
            ]
        })['ids']
        footer_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.PAGE_FOOTER: True}
            ]
        })['ids']
        ids_to_delete: List[str] = header_ids + body_ids + footer_ids
        self.db.delete(ids=ids_to_delete)
        print(f"Deleted {len(ids_to_delete)} page structure docs")

    def create_summary_in_db(self, summary: str):
        """Creates summary in the database."""
        self.db.add_documents(documents=[Document(
            page_content=summary, metadata={ScrapePageGraph.URL: self.url, ScrapePageGraph.SUMMARY: True})])

    def get_summary_from_db(self) -> Optional[str]:
        """Return summary for given URL from db and None if it doesn't exist yet."""
        detailed_summary_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.SUMMARY: True}
            ]
        })
        summary_content: List[str] = detailed_summary_result[ScrapePageGraph.DOCUMENTS]
        if len(summary_content) == 0:
            # Result not in db.
            return None
        if len(summary_content) != 1:
            raise ValueError(
                f"Expected 1 doc for summary result, got: {summary_content}")
        return summary_content[0]

    def delete_summary_from_db(self):
        """Deletes summary from the database."""
        summary_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.SUMMARY: True}
            ]
        })['ids']
        self.db.delete(ids=summary_ids)
        print(f"Deleted {len(summary_ids)} summaries docs")

    def get_all_doc_ids_from_db(self) -> List[str]:
        """Get Ids for all documents (header, footer, body, chunks, summmaries etc.) in the database associated with the given URL."""
        return self.db.get(
            where={ScrapePageGraph.URL: self.url})['ids']

    def get_all_docs_from_db(self) -> List[Document]:
        return self.db.get(where={ScrapePageGraph.URL: self.url})[ScrapePageGraph.DOCUMENTS]

    def delete_all_docs_from_db(self):
        """Delete all documents associated with given url."""
        self.db.delete(ids=self.get_all_doc_ids_from_db())


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
    url = "https://www.forbes.com/sites/adrianbridgwater/2022/08/10/cloudbees-ceo-making-honey-in-the-software-delivery-hive/"
    person_name = "Zach Perret"
    company_name = "Plaid"
    # person_name = "Anuj Kapur"
    # company_name = "Cloudbees"
    graph = ScrapePageGraph(url=url, start_indexing=True)
    # graph.delete_summary_from_db()
    # graph.delete_all_docs_from_db()
    # graph.analyze_page(person_name=person_name, company_name=company_name)
    # print("got: ", graph.get_page_structure_from_db())
    # Write page structure into file to test that it works.

    # print("page body chunks: ", len(graph.page_body_chunks))
    # print(len(graph.get_all_docs_from_db()))
    # print("page structure: ", graph.get_page_structure_from_db())

    # print("delete docs: ", graph.delete_all_docs_from_db())

    # with get_openai_callback() as cb:
    #     page_structure = ScrapePageGraph.get_page_structure(
    #         doc=ScrapePageGraph.fetch_page(url=url))
    #     print(cb)
    #     with open("../example_linkedin_info/page_structure.txt", "w") as f:
    #         f.write(page_structure.to_str())

    # print("num docs: ", len(graph.get_doc_ids()))
    # res = graph.get_summary_from_db()
    # print("summaries exist in db: ", res is not None)
    # graph.analyze_page(person_name=person_name, company_name=company_name)

    # summary = graph.fetch_content_summary()
    # graph.fetch_content_category(
    #     company_name=company_name, person_name=person_name, summary=summary)
    graph.fetch_author_and_date()

    # graph.fetch_content_type(content_details=graph.fetch_author_and_date())

    # user_query = "What is an agent?"
    # docs = graph.retrieve_relevant_docs(user_query=user_query)                                                              

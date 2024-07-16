import os
from dotenv import load_dotenv
import requests
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

load_dotenv()


class ContentSummary(BaseModel):
    """Class to parse content summary from page while parsing it top to bottom."""
    detailed_summary: str = Field(...,
                                  description="Detailed Summary of the text.")


class ContentDetails(BaseModel):
    """Content author and publish date."""
    author: Optional[str] = Field(
        default=None, description="Full name of author of content. If not found, set to None.")
    publish_date: Optional[str] = Field(
        default=None, description="Date when this content was published. If not found, set to None.")


class ContentAboutCompanyOrText(BaseModel):
    """Whether content is about company or text."""
    is_integral_part_of_text: bool = Field(
        ..., description="Set to True if integral part of the text and False otherwise.")
    reason: str = Field(...,
                        description="Reason for why it is integral part of the text.")


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

    # Metadata Constant keys.
    URL = "url"
    CHUNK_SIZE = "chunk_size"
    START_INDEX = "start_index"
    COMBINED_SUMMARIES = "combined_summaries"
    DETAILED_SUMMARY = "detailed_summary"

    def __init__(self, url: str, chunk_size: int = 4096) -> None:
        self.url = url
        self.chunk_size = chunk_size
        self.db = Chroma(persist_directory=ScrapePageGraph.CHROMA_DB_PATH,
                         embedding_function=ScrapePageGraph.OPENAI_EMBEDDING_FUNCTION)
        if len(self.get_doc_ids()) == 0:
            print("Page deos not exist in db, fetching it.")
            # Index page rom URL.
            self.index(url=url, chunk_size=chunk_size)
        else:
            print("Page already exists in db, fetching it.")
            # Get page chunks from database.
            self.chunks = self.get_doc_chunks()

    def index(self, url: str, chunk_size: int):
        """Workflow that fetches HTML page, converts it Markdown doc, splits it and then stores embeddings in a vector database.

        Returns the created Vector database instance which can be used for retrieveing and querying.
        """
        doc: Document = ScrapePageGraph.fetch_page(url=url)
        self.chunks: List[Document] = ScrapePageGraph.split_into_chunks(
            doc=doc, chunk_size=chunk_size)
        self.create_and_store_embeddings()

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

    def fetch_content_summary(self, openai_model_name: str = OPENAI_GPT_3_5_TURBO_MODEL) -> Tuple[str, str]:
        """Fetches content details by parsing the document from the top to the bottom.
        Returns concatenations of summaries as well as overall summary of the page.

        The contents fetched are updated in the output model as we iterate.
        Insipired by the refine chain in the langchain docs.

        Size of compressed content:
        When testing against https://lilianweng.github.io/posts/2023-06-23-agent/
        which is of size = 15 * 4096 characters  ~ 60KB, the compressed text based on summaries is 3500 chars.
        Token size of ChatGPT 3.5 Turbo is 16K tokens so we can index up to web page of size:
        16/3.5 = 4 times the size of 60 KB = 2.4 MB while the compressed doc is still small enough
        to fit the context window.
        """
        summaries = self.get_summaries_from_db()
        if summaries:
            print("Found summaries in database")
            return summaries

        # Do not change this prompt before testing, results may get worse.
        # TODO: Ask to skip parsing HTML navigation, links and javscript. Only parse HTML Body.
        summary_prompt_template = (
            "You are a smart web page analyzer. Assume that the page is being parsed from top to bottom\n"
            "with the 'Context' section containing a summary of text so far and the 'Text' section below\n"
            "containing the new text.\n"
            "Do not make up values for the properties if not found.\n"
            "\n"
            "Context:\n"
            "{context}\n"
            "\n"
            "Text:\n"
            "{text}\n"
        )
        llm = ChatOpenAI(temperature=0, model_name=openai_model_name).with_structured_output(
            ContentSummary)
        prompt = PromptTemplate.from_template(summary_prompt_template)

        # Context will be a concatenated string of summaries
        # computed at each step.
        combined_summaries = ""
        result: ContentSummary
        for i, chunk in enumerate(self.chunks):
            text = chunk.page_content
            chain = prompt | llm
            result: ContentSummary = chain.invoke(
                {"context": combined_summaries, "text": text})
            print(f"\n\nIteration {i+1}")
            print("--------------")
            print(f"Summary so far: {combined_summaries}")

            # Set context as new summary.
            combined_summaries = f"{combined_summaries}\n\n{result.detailed_summary}"

        detailed_summary = result.detailed_summary
        print(f"\n\ndetailed summary: {detailed_summary}")

        # Write summaries to database.
        self.create_summaries_in_db(
            combined_summaries=combined_summaries, detailed_summary=detailed_summary)

        # Return concatenation of summaries and the final detailed summary.
        return combined_summaries, detailed_summary

    def fetch_content_details(self) -> ContentDetails:
        """Fetches content details like author and publish date."""

        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question.\n"
            "If you don't know the answer or it's not in the context, just say you don't know.\n"
            "\n"
            "Question: {question}\n"
            "\n"
            "Context: {context}\n"
        )
        # We want to use latest GPT model because it is likely more accurate than older ones like 3.5 Turbo.
        llm = ChatOpenAI(
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL)
        prompt = PromptTemplate.from_template(prompt_template)

        # We will attempt to fetch content details from top few chunks. Usually its in the beginning of web pages.
        k = 3
        context = ScrapePageGraph.format_docs(self.chunks[:k])
        chain = prompt | llm
        result = chain.invoke(
            {"question": "Who wrote the content and on which date?", "context": context})

        # Now using the string response from LLM, parse it for author and date information.
        content_details = self.parse_llm_output(content=result.content)
        print("\ncontent details about author and publish date: ", content_details)
        return content_details

    def fetch_content_type(self, content_details: ContentDetails, combined_summaries: str) -> str:
        """Fetches content type using given detials and combined summaries of text.

        Currenly returning LLM string output without parsing.
        """
        # Do not change this prompt before testing, results may get worse.
        prompt_template = (
            "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question.\n"
            "If you don't know the answer or it's not in the context, just say you don't know.\n"
            "\n"
            "Question: {question}\n"
            "\n"
            "Context: {context}\n"
        )
        # We want to use latest GPT model because it is likely more accurate than older ones like 3.5 Turbo.
        llm = ChatOpenAI(
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL)
        prompt = PromptTemplate.from_template(prompt_template)

        chain = prompt | llm
        question = "What type of content does this text represent? If you don't know, just say you don't know."
        context = f'URL: {self.url}\n\nAuthor:{content_details.author}\n\nDate published:{content_details.publish_date}\n\nDetailed Summary: {combined_summaries}'
        result = chain.invoke(
            {"question": question, "context": context})

        # Now using the string response from LLM, parse it for author and date information.
        # return self.parse_llm_output(content=result.content)
        print(f"\nContent type:{result}")
        # TODO: Parse content type and return enum. Right now it is just a sentence provided by LLM.
        return result.content

    def is_content_about_company_or_person(self, company_name: str, combined_summaries: str):
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

        question = f"Is {company_name} an integral part of the text below?"
        result = chain.invoke(
            {"question": question, "context": combined_summaries})

        print(f"\n{result}")
        return result

    def parse_llm_output(self, content: str) -> ContentDetails:
        """Helper to fetch content details in structured format from unstructured LLM output.

        Used to process LLM output into content details class.
        """
        prompt_template = (
            "Extract properties of provided function from given content. If a property is not found, set it to None.\n"
            "\n"
            "Content: {content}\n"
        )
        prompt = PromptTemplate.from_template(prompt_template)
        llm = ChatOpenAI(
            temperature=0, model_name=ScrapePageGraph.OPENAI_GPT_4O_MODEL).with_structured_output(ContentDetails)
        chain = prompt | llm
        return chain.invoke(content)

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

        md = markdownify(response.text)
        return Document(page_content=md, metadata={ScrapePageGraph.URL: url})

    @staticmethod
    def split_into_chunks(doc: Document, chunk_size: int = 4096, chunk_overlap: int = 200) -> List[Document]:
        """Split document into chunks of given size and overlap."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True
        )
        chunks = text_splitter.split_documents([doc])
        # Add chunk size metadata.
        for chunk in chunks:
            chunk.metadata[ScrapePageGraph.CHUNK_SIZE] = chunk_size

        print(
            f"Created: {len(chunks)} chunks when splitting: {url} using chunk size: {chunk_size}")

        return chunks

    def create_and_store_embeddings(self):
        """Create embeddings for document chunks and store into vector db."""
        try:
            self.db.add_documents(documents=self.chunks)
        except Exception as e:
            raise ValueError(
                f"Failed to create vector embeddings for {len(self.chunks)} docs with url: {self.url} with error: {e}")

    def get_doc_ids(self) -> List[str]:
        """Get doc Ids stored in database for given URL."""
        return self.db.get(
            where={ScrapePageGraph.URL: self.url})['ids']

    def get_doc_chunks(self) -> List[Document]:
        """Return document chunks sorted by index number from the database for given URL."""
        result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: self.url},
                {ScrapePageGraph.START_INDEX: {"$gte": 0}},
            ]
        })
        sorted_results = sorted(zip(result["metadatas"], result["documents"]),
                                key=lambda m: m[0]["start_index"])

        return [Document(page_content=result[1])
                for result in sorted_results]

    def create_summaries_in_db(self, combined_summaries: str, detailed_summary: str):
        """Creates combined summaries and detailed summary doc in the database."""
        self.db.add_documents(documents=[Document(
            page_content=combined_summaries, metadata={ScrapePageGraph.URL: url, ScrapePageGraph.COMBINED_SUMMARIES: True})])
        self.db.add_documents(documents=[Document(
            page_content=detailed_summary, metadata={ScrapePageGraph.URL: url, ScrapePageGraph.DETAILED_SUMMARY: True})])

    def get_summaries_from_db(self) -> Optional[Tuple[str, str]]:
        """Return combined summaries and detailed summary for given URL from db, none if it doesn't exist yet."""
        combined_summaries_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: url},
                {ScrapePageGraph.COMBINED_SUMMARIES: True}
            ]
        })
        detailed_summary_result: Dict = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: url},
                {ScrapePageGraph.DETAILED_SUMMARY: True}
            ]
        })
        combined_summaries_content: List[str] = combined_summaries_result['documents']
        detailed_summary_content: List[str] = detailed_summary_result['documents']
        if len(combined_summaries_content) == 0 and len(detailed_summary_content) == 0:
            # Result not in db.
            return None
        if len(combined_summaries_content) != 1 or len(detailed_summary_content) != 1:
            raise ValueError(
                f"Expected 1 doc per combined summaries and detailed summary result, got combined: {combined_summaries_content}, detailed: {detailed_summary_content}")
        return combined_summaries_content[0], detailed_summary_content[0]

    def delete_summaries_from_db(self):
        """Deletes combined_summaries and detailed summary from the database."""
        combined_summaries_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: url},
                {ScrapePageGraph.COMBINED_SUMMARIES: True}
            ]
        })['ids']
        detailed_summary_ids: List[str] = self.db.get(where={
            "$and": [
                {ScrapePageGraph.URL: url},
                {ScrapePageGraph.DETAILED_SUMMARY: True}
            ]
        })['ids']
        ids_to_delete: List[str] = combined_summaries_ids + \
            detailed_summary_ids
        self.db.delete(ids=ids_to_delete)
        print(f"Deleted {len(ids_to_delete)} summaries docs")

    def delete_docs(self):
        """Delete docs associated with given url."""
        self.db.delete(ids=self.get_doc_ids())


if __name__ == "__main__":
    # url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
    # url = "https://plaid.com/blog/year-in-review-2023/"
    url = "https://python.langchain.com/v0.2/docs/tutorials/classification/"
    # url = "https://a16z.com/podcast/my-first-16-creating-a-supportive-builder-community-with-plaids-zach-perret/"
    # url = "https://techcrunch.com/2023/09/19/plaids-zack-perret-on-visa-valuations-and-privacy/"
    # url = "https://lattice.com/library/plaids-zach-perret-on-building-a-people-first-organization"
    # url = "https://podcasts.apple.com/us/podcast/zach-perret-ceo-at-plaid/id1456434985?i=1000623440329"
    graph = ScrapePageGraph(url=url)
    # print("docs len: ", len(graph.get_doc_chunks()))
    # print("docs summaries: ", graph.get_summaries_from_db()[0])
    # graph.delete_summaries_from_db()

    # user_query = "What is an agent?"
    # docs = graph.retrieve_relevant_docs(user_query=user_query)
    # print("first doc content: ", docs[0].page_content[:1000])

    with get_openai_callback() as cb:
        combined_summaries, _ = graph.fetch_content_summary()
        content_details = graph.fetch_content_details()
        graph.fetch_content_type(
            content_details=content_details, combined_summaries=combined_summaries)
        # graph.is_content_about_company_or_person(
        #     company_name="Visa", combined_summaries=combined_summaries)

        token_tracker = OpenAITokenTracker(url=graph.url, operation_tag="analyze_page_workflow", prompt_tokens=cb.prompt_tokens,
                                           completion_tokens=cb.completion_tokens, total_tokens=cb.total_tokens, total_cost_in_usd=cb.total_cost)
        print(f"\nTokens used: {token_tracker}")

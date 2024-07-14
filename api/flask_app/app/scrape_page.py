import os
from dotenv import load_dotenv
import requests
from typing import List, Dict
from markdownify import markdownify
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain.chains.summarize import load_summarize_chain

load_dotenv()


class ScrapePageGraph:
    """Uses Langchain to construct a graph that fetches HTML page and parses it into Markdown chunks.

    The class can then be queried multiple times for different answers.
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

    def __init__(self, url: str, chunk_size: int = 4096) -> None:
        self.url = url
        self.chunk_size = chunk_size
        self.db = Chroma(persist_directory=ScrapePageGraph.CHROMA_DB_PATH,
                         embedding_function=ScrapePageGraph.OPENAI_EMBEDDING_FUNCTION)
        if len(self.get_doc_ids()) == 0:
            # Index page rom URL.
            self.index(url=url, chunk_size=chunk_size)
        else:
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

    def get_page_summary(self, openai_model_name: str = OPENAI_GPT_3_5_TURBO_MODEL):
        """Generate a summary of the page contents from chunks."""
        if openai_model_name not in [ScrapePageGraph.OPENAI_GPT_3_5_TURBO_MODEL, ScrapePageGraph.OPENAI_GPT_4O_MODEL]:
            raise ValueError(
                f"Invalid Opena AI model name: {openai_model_name}")

        # Reference: https://python.langchain.com/v0.2/docs/tutorials/summarization.
        llm = ChatOpenAI(temperature=1.0, model_name=openai_model_name)
        chain = load_summarize_chain(llm, chain_type="map_reduce")

        result = chain.invoke(self.chunks)
        return result["output_text"]

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
    def split_into_chunks(doc: Document, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Document]:
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
        result: Dict = self.db.get(
            where={ScrapePageGraph.URL: self.url})
        sorted_results = sorted(zip(result["metadatas"], result["documents"]),
                                key=lambda m: m[0]["start_index"])

        return [Document(page_content=result[1])
                for result in sorted_results]

    def delete_docs(self):
        """Delete docs associated with given url."""
        self.db.delete(ids=self.get_doc_ids())


if __name__ == "__main__":
    url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
    graph = ScrapePageGraph(url=url)

    # user_query = "What is an agent?"
    # docs = graph.retrieve_relevant_docs(user_query=user_query)
    # print("first doc content: ", docs[0].page_content[:1000])

    graph.get_page_summary(
        openai_model_name=ScrapePageGraph.OPENAI_GPT_3_5_TURBO_MODEL)

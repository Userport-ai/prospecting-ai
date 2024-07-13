import os
from dotenv import load_dotenv
from datetime import datetime
from typing import List, Optional
from scrapegraphai.nodes import FetchNode, ParseNode, RAGNode, GenerateAnswerNode
from scrapegraphai.graphs import BaseGraph
from scrapegraphai.models import OpenAI
# Had to import from v1 otherwise ran into ParsedHTMLOutput error during validation.
# Solution suggested here: https://stackoverflow.com/questions/77885715/error-in-pydantic-validation-when-a-class-inherits-from-another-class.
from pydantic.v1 import BaseModel, Field
from langchain_core.documents.base import Document
from langchain_openai import OpenAIEmbeddings
load_dotenv()


class ParsedHTMLOutput(BaseModel):
    """Output from fetching and parsing HTML for a given URL."""
    url: str = Field(...,
                     description="Web URL whose HTML was fetched by the graph.")
    doc: List[Document] = Field(
        ..., description="Langchain Document representing downloaded HTML page as a string.", min_items=1, max_items=2)
    parsed_doc: List[str] = Field(
        ..., description="Parsed HTML page divided into chunks and Markdown formatted.")


class ContentDetails(BaseModel):
    """Class containing summary of the content on the page."""
    summary: str = Field(...,
                         description="Summary of the content on the page.")
    date_published: Optional[datetime] = Field(
        ..., description="Date when this content was published or null if unknown.")
    author: Optional[str] = Field(
        ..., description="Full name of the author of the content and null if not found.")


class ScrapeWebPageGraph:
    """Uses Scrapegraph AI to construct a graph that fetches HTML page and parses it into Markdown chunks.

    The class can then be queried multiple times for different answers.
    """

    # Constant used to store state in graph execution.
    # Some of these values are also field names in ParsedHTMLOuput class, so if you change them here, change them there and vice versa.
    URL = "url"
    DOC = "doc"
    PARSED_DOC = "parsed_doc"
    LLM_MODEL = "llm_model"
    USER_PROMPT = "user_prompt"
    VERBOSE = "verbose"
    RELEVANT_CHUNKS = "relevant_chunks"
    RESULT = "result"

    # Open AI configurations.
    _OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # Available models to use for clients.
    OPENAI_GPT_3_5_TURBO_MODEL = os.getenv("OPENAI_GPT_3_5_TURBO_MODEL")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")

    def __init__(self, url: str, verbose: bool = False, chunk_size: int = 4096) -> None:
        self.chunk_size = chunk_size
        self.verbose = verbose
        self.url = url
        self.parsed_html_output = self._fetch_html_and_parse()

    def _fetch_html_and_parse(self) -> ParsedHTMLOutput:
        """Graph that fetches HTML page and parses it and returns the output."""
        fetch_node = FetchNode(
            input=f"{ScrapeWebPageGraph.URL} | local_dir",
            output=[ScrapeWebPageGraph.DOC],
            node_config={
                "headless": True,
                ScrapeWebPageGraph.VERBOSE: self.verbose,
            }
        )

        parse_node = ParseNode(
            input=ScrapeWebPageGraph.DOC,
            output=[ScrapeWebPageGraph.PARSED_DOC],
            node_config={
                "chunk_size": self.chunk_size,
                ScrapeWebPageGraph.VERBOSE: self.verbose,
            }
        )

        graph = BaseGraph(
            nodes=[
                fetch_node,
                parse_node,
            ],
            edges=[
                (fetch_node, parse_node),
            ],
            entry_point=fetch_node,
            graph_name="fetch_html_and_parse_graph"
        )

        # We need to pass in a random key as first parameter due to a bug in the scrapergraphai library
        # that expects the second argument to be the URL: https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/main/scrapegraphai/graphs/base_graph.py#L117.
        final_state, _ = graph.execute({"random": "not needed",
                                        ScrapeWebPageGraph.URL: self.url})
        return ParsedHTMLOutput(**final_state)

    def invoke(self, user_query: str,  schema: BaseModel, openai_model_name: str = OPENAI_GPT_4O_MODEL):
        """Runs user query against content of the web page and returns the answer."""
        # Define the configuration for the graph
        graph_config = {
            "llm": {
                "api_key": ScrapeWebPageGraph._OPENAI_API_KEY,
                "model": openai_model_name,
                "temperature": 1.0,
            },
        }

        llm_model = OpenAI(graph_config["llm"])
        embedder = OpenAIEmbeddings(api_key=llm_model.openai_api_key)
        rag_node = RAGNode(
            input=f"{ScrapeWebPageGraph.USER_PROMPT} & {ScrapeWebPageGraph.PARSED_DOC}",
            output=[ScrapeWebPageGraph.RELEVANT_CHUNKS],
            node_config={
                ScrapeWebPageGraph.LLM_MODEL: llm_model,
                "embedder_model": embedder,
                ScrapeWebPageGraph.VERBOSE: self.verbose,
                "cache_path": "cache"
            }
        )
        generate_answer_node = GenerateAnswerNode(
            input=f"{ScrapeWebPageGraph.USER_PROMPT} & {ScrapeWebPageGraph.RELEVANT_CHUNKS}",
            output=[ScrapeWebPageGraph.RESULT],
            node_config={
                ScrapeWebPageGraph.LLM_MODEL: llm_model,
                ScrapeWebPageGraph.VERBOSE: self.verbose,
                "schema": schema,
            }
        )

        graph = BaseGraph(
            nodes=[
                rag_node,
                generate_answer_node,
            ],
            edges=[
                (rag_node, generate_answer_node),
            ],
            entry_point=rag_node,
            graph_name="rag_and_generate_answer_graph"
        )
        final_state, _ = graph.execute(
            {ScrapeWebPageGraph.USER_PROMPT: user_query, ScrapeWebPageGraph.PARSED_DOC: self.parsed_html_output.parsed_doc})
        print(final_state.keys())
        print(final_state[ScrapeWebPageGraph.RESULT])


if __name__ == "__main__":
    graph = ScrapeWebPageGraph(
        "https://lilianweng.github.io/posts/2023-06-23-agent/", verbose=True, chunk_size=500)
    graph.invoke(user_query="What is this article about? Explain in 100 words or less.",
                 schema=ContentDetails, openai_model_name=ScrapeWebPageGraph.OPENAI_GPT_3_5_TURBO_MODEL)

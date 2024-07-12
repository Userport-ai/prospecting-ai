import os
from dotenv import load_dotenv
from typing import List
from scrapegraphai.nodes import FetchNode, ParseNode
from scrapegraphai.graphs import BaseGraph
# Had to import from v1 otherwise ran into ParsedHTMLOutput error during validation.
# Solution suggested here: https://stackoverflow.com/questions/77885715/error-in-pydantic-validation-when-a-class-inherits-from-another-class.
from pydantic.v1 import BaseModel, Field
from langchain_core.documents.base import Document

load_dotenv()


class ParsedHTMLOutput(BaseModel):
    """Output from fetching and parsing HTML for a given URL."""
    url: str = Field(...,
                     description="Web URL whose HTML was fetched by the graph.")
    doc: List[Document] = Field(
        ..., description="Langchain Document representing downloaded HTML page as a string.", min_items=1, max_items=2)
    parsed_doc: List[str] = Field(
        ..., description="Parsed HTML page divided into chunks and Markdown formatted.")


class ScrapeWebPageGraph:
    """Uses Scrapegraph AI to construct a graph that fetches HTML page and parses it into Markdown chunks.

    The class can then be queried multiple times for different answers.
    """

    # Constant used to store state in graph execution.
    # If these values are changed, you must change the corresponding field names in ParsedHTMLOuput class.
    URL = "url"
    DOC = "doc"
    PARSED_DOC = "parsed_doc"

    # Open AI configurations.
    _OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # Available models to use for clients.
    OPENAI_GPT_3_5_TURBO_MODEL = os.getenv("OPENAI_GPT_3_5_TURBO_MODEL")
    OPENAI_GPT_4O_MODEL = os.getenv("OPENAI_GPT_4O_MODEL")
    GPT_40_MAX_CONTEXT_WINDOW_SIZE = 128000
    GPT_3_5_TURBO_MAX_CONTEXT_WINDOW_SIZE = 16000

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
                "verbose": self.verbose,
            }
        )

        parse_node = ParseNode(
            input=ScrapeWebPageGraph.DOC,
            output=[ScrapeWebPageGraph.PARSED_DOC],
            node_config={
                "chunk_size": self.chunk_size,
                "verbose": self.verbose,
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
            entry_point=fetch_node
        )

        # We need to pass in a random key as first parameter due to a bug in the scrapergraphai library
        # that expects the second argument to be the URL: https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/main/scrapegraphai/graphs/base_graph.py#L117.
        final_state, _ = graph.execute({"random": "not needed",
                                        ScrapeWebPageGraph.URL: self.url})
        return ParsedHTMLOutput(**final_state)


if __name__ == "__main__":
    graph = ScrapeWebPageGraph(
        "https://lilianweng.github.io/posts/2023-06-23-agent/")

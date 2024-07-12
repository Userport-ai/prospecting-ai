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


class FetchHTMLGraph:
    """Uses Scrapegraph AI to construct a graph that fetches HTML page and parses it into Markdown chunks."""

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

    def __init__(self, verbose: bool = False, chunk_size: int = 4096) -> None:
        self.chunk_size = chunk_size
        self.verbose = verbose
        self.html_fetch_and_parse_graph = self._create_html_fetch_and_parse_graph()

    def _create_html_fetch_and_parse_graph(self) -> BaseGraph:
        """Define graph to fetch HTML page and parse the document into a list of chunked Langchain documents."""

        fetch_node = FetchNode(
            input=f"{FetchHTMLGraph.URL} | local_dir",
            output=[FetchHTMLGraph.DOC],
            node_config={
                "headless": True,
                "verbose": self.verbose,
            }
        )

        parse_node = ParseNode(
            input=FetchHTMLGraph.DOC,
            output=[FetchHTMLGraph.PARSED_DOC],
            node_config={
                "chunk_size": self.chunk_size,
                "verbose": self.verbose,
            }
        )

        return BaseGraph(
            nodes=[
                fetch_node,
                parse_node,
            ],
            edges=[
                (fetch_node, parse_node),
            ],
            entry_point=fetch_node
        )

    def run(self, url: str) -> ParsedHTMLOutput:
        """Fetches and parses HTML page associated with the given URL."""

        # We need to pass in a random key as first parameter due to a bug in the scrapergraphai library
        # that expects the second argument to be the URL: https://github.com/ScrapeGraphAI/Scrapegraph-ai/blob/main/scrapegraphai/graphs/base_graph.py#L117.
        final_state, _ = self.html_fetch_and_parse_graph.execute({"random": "not needed",
                                                                  FetchHTMLGraph.URL: url})
        return ParsedHTMLOutput(**final_state)


if __name__ == "__main__":
    g = FetchHTMLGraph()
    url = "https://lilianweng.github.io/posts/2023-06-23-agent/"
    g.run(url=url)

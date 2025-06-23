#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Custom callbacks for controlling output in the deep research tool.
"""

from typing import Any, Dict, List, Optional
from langchain_core.callbacks.base import BaseCallbackHandler
from langchain_core.utils import print_text

class SilentToolCallbackHandler(BaseCallbackHandler):
    """Callback handler that prints everything except tool outputs."""

    def __init__(self, color: Optional[str] = None) -> None:
        """Initialize callback handler.

        Args:
            color: The color to use for text (not for tool output). Defaults to None.
        """
        self.color = color

    def on_chain_start(
        self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any
    ) -> None:
        """Print out that we are entering a chain.

        Args:
            serialized: The serialized chain.
            inputs: The inputs to the chain.
            **kwargs: Additional keyword arguments.
        """
        if "name" in kwargs:
            name = kwargs["name"]
        elif serialized:
            name = serialized.get("name", serialized.get("id", ["<unknown>"])[-1])
        else:
            name = "<unknown>"
        print(f"\n\n\033[1m> Entering new {name} chain...\033[0m")

    def on_chain_end(self, outputs: Dict[str, Any], **kwargs: Any) -> None:
        """Print out that we finished a chain.

        Args:
            outputs: The outputs of the chain.
            **kwargs: Additional keyword arguments.
        """
        print("\n\033[1m> Finished chain.\033[0m")

    def on_agent_action(
        self, action: Any, color: Optional[str] = None, **kwargs: Any
    ) -> Any:
        """Run on agent action.

        Args:
            action: The agent action.
            color: The color to use for the text. Defaults to None.
            **kwargs: Additional keyword arguments.
        """
        print_text(action.log, color=color or self.color)

    def on_tool_end(
        self,
        output: Any,
        color: Optional[str] = None,
        observation_prefix: Optional[str] = None,
        llm_prefix: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        """Print tool output without color.

        Args:
            output: The output to print.
            color: The color parameter is ignored to avoid blue text.
            observation_prefix: The observation prefix.
            llm_prefix: The LLM prefix.
            **kwargs: Additional keyword arguments.
        """
        output = str(output)
        if observation_prefix is not None:
            print(f"\n{observation_prefix}")
        
        # Print without color to avoid blue text
        print(output)
        
        if llm_prefix is not None:
            print(f"\n{llm_prefix}")

    def on_text(
        self,
        text: str,
        color: Optional[str] = None,
        end: str = "",
        **kwargs: Any,
    ) -> None:
        """Print text.

        Args:
            text: The text to print.
            color: The color to use for the text. Defaults to None.
            end: The end character to use. Defaults to "".
            **kwargs: Additional keyword arguments.
        """
        print_text(text, color=color or self.color, end=end)

    def on_agent_finish(
        self, finish: Any, color: Optional[str] = None, **kwargs: Any
    ) -> None:
        """Print agent finish.

        Args:
            finish: The agent finish.
            color: The color to use for the text. Defaults to None.
            **kwargs: Additional keyword arguments.
        """
        print_text(finish.log, color=color or self.color, end="\n")
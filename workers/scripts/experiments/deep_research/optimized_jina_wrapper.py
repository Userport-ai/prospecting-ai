#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Optimized Jina search wrapper that reduces token consumption while maintaining quality.
"""

import re
from typing import Dict, List, Any

from bs4 import BeautifulSoup
from langchain_community.utilities.jina_search import JinaSearchAPIWrapper


class OptimizedJinaSearchAPIWrapper(JinaSearchAPIWrapper):
    """Optimized Jina search wrapper with token reduction strategies."""
    
    def __init__(
        self, 
        max_results: int = 5,
        max_content_length: int = 1000,
        extract_relevant_content: bool = True,
        **kwargs
    ):
        """
        Initialize the optimized wrapper.
        
        Args:
            max_results: Maximum number of search results to return (default: 5)
            max_content_length: Maximum characters per result content (default: 1000)
            extract_relevant_content: Whether to extract only relevant content (default: True)
        """
        super().__init__(**kwargs)
        # Store custom attributes using __dict__ to bypass pydantic validation
        self.__dict__['max_results'] = max_results
        self.__dict__['max_content_length'] = max_content_length
        self.__dict__['extract_relevant_content'] = extract_relevant_content
    
    def _search_request(self, query: str) -> List[Dict[str, Any]]:
        """
        Override the search request to limit and optimize results.
        """
        # Get original results from parent class
        try:
            results = super()._search_request(query)
        except Exception as e:
            # If there's an error, return empty results
            return []
        
        # Limit number of results
        if isinstance(results, list):
            results = results[:self.max_results]
        
        # Process each result to reduce token usage
        optimized_results = []
        for result in results:
            optimized_result = self._optimize_result(result, query)
            if optimized_result:
                optimized_results.append(optimized_result)
        
        return optimized_results
    
    def _optimize_result(self, result: Dict[str, Any], query: str) -> Dict[str, Any]:
        """
        Optimize a single search result to reduce token usage.
        """
        optimized = {}
        
        # Keep essential metadata
        if 'title' in result:
            optimized['title'] = result['title']
        if 'url' in result:
            optimized['url'] = result['url']
        if 'description' in result:
            optimized['description'] = result['description'][:300]  # Limit description
        
        # Process content field
        if 'content' in result and result['content']:
            content = result['content']
            
            if self.extract_relevant_content:
                # Extract only relevant content around keywords
                relevant_content = self._extract_relevant_content(content, query)
                optimized['content'] = relevant_content
            else:
                # Just truncate content
                optimized['content'] = content[:self.max_content_length]
        
        return optimized
    
    def _extract_relevant_content(self, content: str, query: str) -> str:
        """
        Extract only the most relevant parts of the content based on the query.
        """
        if not content:
            return ""
        
        # Clean HTML if present
        if '<' in content and '>' in content:
            try:
                soup = BeautifulSoup(content, 'html.parser')
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                content = soup.get_text(separator=' ', strip=True)
            except:
                pass
        
        # Split query into keywords
        keywords = [word.lower() for word in query.split() if len(word) > 2]
        
        # Find sentences containing keywords
        sentences = re.split(r'[.!?]+', content)
        relevant_sentences = []

        for i, sentence in enumerate(sentences):
            sentence_lower = sentence.lower()
            # Score each sentence by keyword matches
            score = sum(1 for keyword in keywords if keyword in sentence_lower)
            if score > 0:
                relevant_sentences.append((score, i, str(sentence.strip())))
        
        # Sort by score (descending) and then by position
        relevant_sentences.sort(key=lambda x: (-x[0], x[1]))
        
        # If we found relevant sentences, use them
        if relevant_sentences:
            # Take the best sentences up to max length
            selected_content = []
            current_length = 0
            
            for score, pos, sentence in relevant_sentences:
                sentence_with_sep = sentence + '. '
                if current_length + len(sentence_with_sep) <= self.max_content_length:
                    selected_content.append(sentence)
                    current_length += len(sentence_with_sep)
                else:
                    # Add partial sentence if there's room
                    remaining = self.max_content_length - current_length
                    if remaining > 50:  # Only add if meaningful length remains
                        selected_content.append(sentence[:remaining-3] + "...")
                    break
            
            return '. '.join(selected_content)
        else:
            # No keyword matches - try to find the most content-rich paragraph
            # Skip short paragraphs that are likely headers/navigation
            paragraphs = content.split('\n\n')
            content_paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 100]
            
            if content_paragraphs:
                # Use the first substantial paragraph
                return content_paragraphs[0][:self.max_content_length] + "..."
            else:
                # Fallback: Skip the first 200 chars (likely header) and take from middle
                if len(content) > 200:
                    start_pos = min(200, len(content) // 4)  # Start from 1/4 into content
                    return content[start_pos:start_pos + self.max_content_length] + "..."
                else:
                    return content[:self.max_content_length] + "..."
    
    def run(self, query: str) -> str:
        """
        Override run method to format optimized results.
        """
        results = self._search_request(query)
        
        if not results:
            return "No results found."
        
        # Format results in a concise way
        formatted_results = []
        for i, result in enumerate(results, 1):
            parts = [f"\n{i}. {result.get('title', 'No title')}"]
            
            if 'url' in result:
                parts.append(f"   URL: {result['url']}")
            
            if 'description' in result:
                parts.append(f"   Summary: {result['description']}")
            
            if 'content' in result and result['content']:
                parts.append(f"   Relevant Content: {result['content']}")
            
            formatted_results.append('\n'.join(parts))
        
        return '\n'.join(formatted_results)


class TwoPhaseJinaSearchAPIWrapper(OptimizedJinaSearchAPIWrapper):
    """
    Two-phase Jina search wrapper that fetches metadata first, then content for selected results.
    """
    
    def __init__(
        self,
        metadata_only_threshold: int = 3,
        **kwargs
    ):
        """
        Initialize two-phase wrapper.
        
        Args:
            metadata_only_threshold: Number of results to fetch full content for
        """
        super().__init__(**kwargs)
        self.__dict__['metadata_only_threshold'] = metadata_only_threshold
    
    def _search_request(self, query: str) -> List[Dict[str, Any]]:
        """
        Implement two-phase search: metadata first, then selective content.
        """
        # Phase 1: Get metadata for all results
        results = super()._search_request(query)
        
        if not results:
            return []

        # Phase 2: Keep full content for top results, snippets for others
        # Trust Jina's ranking - they do sophisticated relevance scoring
        
        for i, result in enumerate(results):
            if i >= self.metadata_only_threshold and 'content' in result:
                # For results beyond threshold, replace content with description (snippet)
                # The description field contains the search snippet which is more relevant
                if 'description' in result and result['description']:
                    result['content'] = result['description']
                else:
                    # Fallback: use our extraction if no description
                    content = result['content']
                    relevant_snippet = self._extract_relevant_content(content, query)
                    result['content'] = relevant_snippet[:300] + "..."
        
        return results
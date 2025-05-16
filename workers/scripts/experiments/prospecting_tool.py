#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Prospecting Tool - Research prospective accounts for a specific product or company

This script takes a product/company that you're selling and a list of target companies,
then performs in-depth research to identify fit, pain points, and sales opportunities.
"""

import os
import csv
import json
import asyncio
import argparse
import sqlite3
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
import pandas as pd
import uuid

# Try to import DuckDB if available
try:
    import duckdb
    DUCKDB_AVAILABLE = True
except ImportError:
    DUCKDB_AVAILABLE = False

# LangChain imports
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools.jina_search import JinaSearch
from langchain_community.utilities.jina_search import JinaSearchAPIWrapper
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, SecretStr

# For JSON repair - optional dependency
try:
    from json_repair import loads as repair_loads
except ImportError:
    import json
    repair_loads = json.loads
    print("Warning: json_repair not found, using standard json.loads instead")


###############################
# Timeout Configuration
###############################

# Central place to configure all timeouts
TIMEOUTS = {
    # Agent timeouts
    "agent_max_iterations": 12,       # Maximum iterations for agents
    "agent_execution_time": 600,      # 10 minutes max per agent execution
    
    # Step timeouts
    "research_step": 1200,            # 20 minutes per research step
    "validation_step": 600,           # 10 minutes for validation
    
    # Overall workflow timeouts
    "account_research": 3600,         # 1 hour per account
    "batch_processing": 36000         # 10 hours for the entire batch
}


###############################
# Data Models
###############################

class ResearchStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class FitLevel(str, Enum):
    EXCELLENT = "excellent"    # Highly relevant, multiple pain points, strong opportunity
    GOOD = "good"              # Relevant, some clear pain points, good opportunity
    MODERATE = "moderate"      # Some relevance, potential pain points
    POOR = "poor"              # Limited relevance, few pain points
    UNSUITABLE = "unsuitable"  # Not a fit for the product
    UNKNOWN = "unknown"        # Not yet evaluated


@dataclass
class ProspectingTarget:
    """A target company for prospecting analysis"""
    company_name: str
    website: str
    industry: str = ""
    description: str = ""
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualificationSignal:
    """A signal for qualifying prospective accounts"""
    name: str
    description: str
    importance: int = 5  # Scale of 1-5, with 5 being most important
    is_confirmed: bool = False
    detection_instructions: str = ""  # Instructions for detecting this signal in research
    
    def __str__(self):
        return f"{self.name} - {self.description} (Importance: {self.importance})"


@dataclass
class SellingProduct:
    """The product/company that you're selling"""
    name: str
    website: str
    description: str = ""
    value_proposition: str = ""
    key_features: List[str] = field(default_factory=list)
    target_industries: List[str] = field(default_factory=list)
    ideal_customer_profile: str = ""
    competitor_alternatives: List[str] = field(default_factory=list)
    qualification_signals: List[QualificationSignal] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchStepResult:
    step_id: str
    question: str
    answer: str
    status: ResearchStatus = ResearchStatus.PENDING
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.UNKNOWN
    sources: List[str] = field(default_factory=list)
    validation_status: Optional[str] = None
    validation_notes: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class MatchedSignal:
    """A qualification signal that matched with the target company"""
    name: str
    description: str = ""
    importance: int = 5  # Scale of 1-5, with 5 being most important
    evidence: str = ""  # Evidence from research supporting this match


@dataclass
class ProspectingResult:
    """Result of prospecting research for a single target company"""
    target: ProspectingTarget
    selling_product: SellingProduct
    fit_level: FitLevel = FitLevel.UNKNOWN
    fit_score: float = 0.0  # 0.0 to 1.0
    fit_explanation: str = ""
    pain_points: List[str] = field(default_factory=list)
    value_propositions: List[str] = field(default_factory=list)
    objection_handling: List[str] = field(default_factory=list)
    key_decision_makers: List[str] = field(default_factory=list)
    matched_signals: List[MatchedSignal] = field(default_factory=list)  # List of qualification signals that match
    steps: Dict[str, ResearchStepResult] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    overall_status: ResearchStatus = ResearchStatus.PENDING
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert Enum types to strings for better JSON serialization
        result["fit_level"] = self.fit_level.value if isinstance(self.fit_level, Enum) else self.fit_level
        result["overall_status"] = self.overall_status.value if isinstance(self.overall_status, Enum) else self.overall_status
        
        # Ensure matched_signals are properly serialized
        if "matched_signals" in result and result["matched_signals"]:
            result["matched_signals"] = [asdict(signal) for signal in self.matched_signals]
            
        return result
    
    def mark_completed(self):
        self.completed_at = datetime.now().isoformat()
        self.overall_status = ResearchStatus.COMPLETED


class ResearchStep(BaseModel):
    step_id: str = Field(..., description="Unique identifier for this research step")
    question: str = Field(..., description="Research question to answer")
    prompt_template: str = Field(..., description="Template for the research prompt")
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this depends on")
    validate_with_search: bool = Field(default=True, description="Whether to validate results with search")


###############################
# Core Research Engine
###############################

class ProspectingResearchEngine:
    """Engine for performing deep research on prospective accounts."""
    
    def __init__(
        self, 
        selling_product: SellingProduct,
        model_name: str = "gemini-2.5-flash-preview-04-17",
        verbose: bool = True, 
        selling_product_research: str = ""
    ):
        self.verbose = verbose
        self.model_name = model_name
        self.selling_product = selling_product
        self.selling_product_research = selling_product_research
        
        # Configure LLM
        if "gemini" in model_name.lower():
            google_api_key = os.getenv("GEMINI_API_TOKEN")
            if not google_api_key:
                raise ValueError("GEMINI_API_TOKEN environment variable must be set")

            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.2,
                google_api_key=google_api_key
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")
        
        # Set up search tools
        self.search_tools = self._setup_search_tools()
        
        # Set up research agents
        self.research_agent = self._create_research_agent()
        self.validation_agent = self._create_validation_agent()
    
    @staticmethod
    def _setup_search_tools() -> List[BaseTool]:
        """Set up search tools for research and validation."""
        tools = []

        # Set up Jina search if API key is available
        jina_api_key_value = os.getenv("JINA_API_TOKEN")
        if jina_api_key_value:
            jina_wrapper = JinaSearchAPIWrapper(
                api_key=SecretStr(jina_api_key_value)
                # JinaSearchAPIWrapper doesn't support timeout parameter
            )
            jina_tool = JinaSearch(search_wrapper=jina_wrapper)
            jina_tool.description = """Searches the web using Jina's AI-powered search. 
            Use this for finding specific facts and information about companies, products, 
            recent events, or market data."""
            tools.append(jina_tool)

        # Set up DuckDuckGo as fallback
        # DuckDuckGoSearchRun doesn't accept timeout parameter directly
        ddg_tool = DuckDuckGoSearchRun()
        ddg_tool.name = "duckduckgo_search"
        ddg_tool.description = """FALLBACK TOOL: **Use only if Jina doesn't find information**.
        Good for general verification but less reliable for exact numbers."""
        tools.append(ddg_tool)

        return tools
    
    def _create_research_agent(self) -> AgentExecutor:
        """Create a LangChain agent for performing research."""
        system_prompt = """You are an expert B2B sales and account research specialist.
        Your task is to research companies to identify sales opportunities, pain points, and fit with a product.
        
        RESEARCH PROCESS:
        1. Understand the research question clearly
        2. Break down the question into key aspects to research
        3. Formulate precise search queries for each aspect
        4. Execute searches using the provided tools
        5. Analyze search results for relevance and credibility
        6. Perform additional searches if information is incomplete
        7. Synthesize findings into a comprehensive, factual answer
        
        IMPORTANT GUIDELINES:
        - Be thorough and methodical in your research
        - Focus on factual, verifiable information
        - Pay attention to recency - prefer newer information
        - Cite sources by linking to them
        - Think step-by-step and document your reasoning
        - Focus on B2B sales-relevant information
        - Look for business pain points and opportunities
        
        When formulating your final answer:
        1. Provide comprehensive but concise information
        2. Organize information in a clear, logical structure
        3. Include ONLY facts that you verified through search
        4. Cite your sources inline when stating specific facts
        5. Present balanced information, avoiding bias
        6. Identify where information might be uncertain or conflicting
        
        Your goal is to produce accurate, actionable research that helps B2B sales teams 
        understand potential accounts and identify sales opportunities.
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, self.search_tools, prompt)

        memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")

        return AgentExecutor(
            agent=agent,
            tools=self.search_tools,
            verbose=self.verbose,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=TIMEOUTS["agent_max_iterations"],
            max_execution_time=TIMEOUTS["agent_execution_time"]
        )
    
    def _create_validation_agent(self) -> AgentExecutor:
        """Create a LangChain agent for validating research."""
        system_prompt = """You are a B2B sales data fact validator. Your task is to verify AI-generated answers 
        about companies, markets, and sales information.
        
        Follow this validation process:
        1. First, identify 2-3 specific claims in the answer that are critical to validate. Make sure the claims are critical for the answer to be factually correct in response to the question asked.
        2. For each claim, formulate a precise search query. Verify all the data with web search including any information provided as part of context in the query.
        3. Execute the search and analyze the results
        4. Perform more searches **only if needed**.
        5. Assimilate and compare the search results to the original claim - is it confirmed, contradicted, or inconclusive?
        6. After checking all claims, provide an overall validation assessment
        
        Think step-by-step and document your reasoning clearly. Be thorough in your analysis
        of the search results, noting when information is confirmed or contradicted.
        
        IMPORTANT: You MUST verify multiple claims before concluding. 
        E.g.:
            - Search claim 1 → Analyze results
            - Search claim 2 → Analyze results  
            - Compare only then provide final JSON assessment
        Never conclude after just one search unless you find contradictory evidence.

        
        End your analysis with a JSON validation result formatted exactly like this:
        ```json
        {{
          "validation_status": "validated_correct",
          "confidence": 0.8,
          "validation_notes": "Your reasoning here",
          "corrected_answer": "Corrected version if needed, or null",
          "sources": ["[sources](in markdown format)"]
        }}
        ```
        
        Validation status meanings:
        - "validated_correct": Answer verified and confirmed to be accurate
        - "validated_incorrect": Answer contains factual errors that need correction
        - "validation_failed": Unable to properly validate due to technical issues
        - "insufficient_data": Not enough information found to validate conclusively
        
        Keep the JSON structure exactly as shown, with those exact field names.
        """

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(self.llm, self.search_tools, prompt)

        memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")

        return AgentExecutor(
            agent=agent,
            tools=self.search_tools,
            verbose=self.verbose,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=TIMEOUTS["agent_max_iterations"],
            max_execution_time=TIMEOUTS["agent_execution_time"]
        )
    
    async def research_step(
        self, 
        target: ProspectingTarget, 
        step: ResearchStep,
        previous_results: Dict[str, ResearchStepResult] = None
    ) -> ResearchStepResult:
        """Execute a single research step for a target company."""
        try:
            if previous_results is None:
                previous_results = {}
            
            # Prepare context from previous steps
            context = {}
            for dep_id in step.depends_on:
                if dep_id in previous_results:
                    context[dep_id] = previous_results[dep_id].answer
            
            # Format the research prompt
            research_prompt = self._format_research_prompt(
                target=target,
                step=step,
                context=context
            )
            
            if self.verbose:
                print(f"\n--- Researching {step.step_id} for {target.company_name} ---")
            
            # Execute research with timeout
            try:
                agent_result = await asyncio.wait_for(
                    self.research_agent.ainvoke({"input": research_prompt}),
                    timeout=TIMEOUTS["research_step"]
                )
                answer = agent_result.get("output", "")
                
                result = ResearchStepResult(
                    step_id=step.step_id,
                    question=step.question,
                    answer=answer,
                    status=ResearchStatus.COMPLETED,
                    confidence=0.7,  # Initial confidence before validation
                    confidence_level=ConfidenceLevel.MEDIUM
                )
                
            except asyncio.TimeoutError:
                if self.verbose:
                    print(f"Research step {step.step_id} timed out after {TIMEOUTS['research_step']} seconds")
                
                return ResearchStepResult(
                    step_id=step.step_id,
                    question=step.question,
                    answer="Research timed out. The research process exceeded the allocated time limit.",
                    status=ResearchStatus.TIMEOUT,
                    confidence=0.1,
                    confidence_level=ConfidenceLevel.LOW,
                    error=f"Timed out after {TIMEOUTS['research_step']} seconds"
                )
            
            # Validate if required
            if step.validate_with_search:
                result = await self._validate_result(target, step, result)
                
            return result
        
        except Exception as e:
            error_msg = f"Error in research step {step.step_id}: {str(e)}"
            if self.verbose:
                print(f"ERROR: {error_msg}")
            
            return ResearchStepResult(
                step_id=step.step_id,
                question=step.question,
                answer="",
                status=ResearchStatus.FAILED,
                confidence=0.0,
                confidence_level=ConfidenceLevel.UNKNOWN,
                error=error_msg
            )
    
    def _format_research_prompt(
        self, 
        target: ProspectingTarget, 
        step: ResearchStep,
        context: Dict[str, str]
    ) -> str:
        """Format the research prompt with target info, selling product, and context from previous steps."""
        # Target company information
        target_info = f"""
        TARGET COMPANY INFORMATION:
        - Name: {target.company_name}
        - Website: {target.website}
        - Industry: {target.industry if target.industry else "Unknown"}
        - Description: {target.description if target.description else "No description available"}
        """
        
        # Selling product information
        product_info = f"""
        SELLING PRODUCT INFORMATION:
        - Product/Company: {self.selling_product.name}
        - Website: {self.selling_product.website}
        """
        
        # Format previous research context if available
        previous_research = ""
        if context:
            previous_research = "PREVIOUS RESEARCH FINDINGS:\n"
            for step_id, answer in context.items():
                previous_research += f"- {step_id}: {answer}\n"
        
        # Process template to handle special placeholders
        template = step.prompt_template
        
        # Replace {selling_product_info} with the actual selling product research
        if "{selling_product_info}" in template:
            # Include qualification signals if available
            qualification_signals_text = ""
            if self.selling_product.qualification_signals:
                qualification_signals_text = "\nQUALIFICATION SIGNALS TO CHECK FOR:\n"
                for signal in self.selling_product.qualification_signals:
                    if signal.is_confirmed:
                        qualification_signals_text += f"- {signal.name} (Importance: {signal.importance}/5)\n  Description: {signal.description}\n  Detection Instructions: {signal.detection_instructions}\n"
            
            selling_product_info = f"""
            Product/Company: {self.selling_product.name}
            Website: {self.selling_product.website}
            
            {self.selling_product_research}
            {qualification_signals_text}
            """
            template = template.replace("{selling_product_info}", selling_product_info)
        
        # Combine everything
        prompt = f"""
        {target_info}
        
        {product_info}
        
        {previous_research if previous_research else ""}
        
        RESEARCH QUESTION: {step.question}
        
        {template}
        
        Please conduct thorough research to answer this question. Use search tools to find
        accurate, up-to-date information about the target company. Document your research process and cite your sources.
        Keep in mind the selling product context when researching to identify relevant pain points and opportunities.
        """
        
        return prompt
    
    async def _validate_result(
        self, 
        target: ProspectingTarget, 
        step: ResearchStep, 
        result: ResearchStepResult
    ) -> ResearchStepResult:
        """Validate a research result using search."""
        try:
            if self.verbose:
                print(f"\n--- Validating {step.step_id} for {target.company_name} ---")
                
            validation_prompt = f"""
            Validate this sales research answer:
            
            QUESTION: <question> {step.question} </question>
            
            CLAIMED ANSWER(NEED TO VALIDATE): <answer> {result.answer} </answer>
            
            COMPANY INFORMATION: <context> 
            - Name: {target.company_name}
            - Website: {target.website}
            - Industry: {target.industry if target.industry else "Unknown"}
            </context>
            
            INSTRUCTIONS:
            1. Identify 2-3 critical claims that need verification
            2. Search for relevant information using the search tools
            3. Evaluate if the search results CONFIRM or CONTRADICT the claims
            4. Provide a final validation with confidence score
            
            After your analysis, provide a JSON validation result with these fields:
            "validation_status" (one of: "validated_correct", "validated_incorrect", "validation_failed", "insufficient_data"),
            "confidence" (float from 0.0 to 1.0),
            "validation_notes" (your assessment explanation),
            "corrected_answer" (corrected answer if the original has factual errors, or null),
            "sources" (array of sources used for validation)
            """
            
            # Run validation agent with timeout
            try:
                agent_result = await asyncio.wait_for(
                    self.validation_agent.ainvoke({"input": validation_prompt}),
                    timeout=TIMEOUTS["validation_step"]
                )
                agent_output = agent_result.get("output", "")
                
                # Extract validation JSON
                validation_result = self._extract_json_from_text(agent_output)
                
                if not validation_result or not isinstance(validation_result, dict):
                    validation_result = {
                        "validation_status": "validation_failed",
                        "confidence": 0.5,
                        "validation_notes": "Validation failed: Agent did not return proper validation result",
                        "corrected_answer": None,
                        "sources": []
                    }
            
            except asyncio.TimeoutError:
                if self.verbose:
                    print(f"Validation for step {step.step_id} timed out after {TIMEOUTS['validation_step']} seconds")
                
                validation_result = {
                    "validation_status": "validation_failed",
                    "confidence": 0.3,
                    "validation_notes": f"Validation timed out after {TIMEOUTS['validation_step']} seconds",
                    "corrected_answer": None,
                    "sources": []
                }
            
            # Update result with validation information
            updated_result = ResearchStepResult(
                step_id=result.step_id,
                question=result.question,
                answer=validation_result.get("corrected_answer", result.answer) if validation_result.get("validation_status") == "validated_incorrect" else result.answer,
                status=result.status,
                validation_status=validation_result.get("validation_status"),
                validation_notes=validation_result.get("validation_notes"),
                sources=validation_result.get("sources", []),
                error=result.error
            )
            
            # Adjust confidence based on validation
            validation_status = validation_result.get("validation_status")
            validation_confidence = validation_result.get("confidence", 0.5)
            
            if validation_status == "validated_correct":
                updated_result.confidence = min(0.95, 0.7 + validation_confidence * 0.3)
                updated_result.confidence_level = ConfidenceLevel.HIGH
            elif validation_status == "validated_incorrect":
                updated_result.confidence = max(0.3, validation_confidence)
                updated_result.confidence_level = ConfidenceLevel.LOW
            elif validation_status == "insufficient_data":
                updated_result.confidence = 0.5
                updated_result.confidence_level = ConfidenceLevel.MEDIUM
            else:  # validation_failed
                updated_result.confidence = 0.4
                updated_result.confidence_level = ConfidenceLevel.LOW
            
            return updated_result
        
        except Exception as e:
            # If validation fails, return original result with a note
            result.validation_status = "validation_failed"
            result.validation_notes = f"Validation error: {str(e)}"
            return result
    
    @staticmethod
    def _extract_json_from_text(text: str) -> Dict[str, Any]:
        """Extract JSON content from text response."""
        try:
            # Find JSON block in triple backticks
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            
            if json_match:
                json_str = json_match.group(1)
                return repair_loads(json_str)
            
            # If no JSON block found, try to repair the entire text
            return repair_loads(text)
        except Exception as e:
            print(f"Error parsing JSON response: {str(e)}")
            return {}


###############################
# Prospecting Workflow
###############################

class ProspectingWorkflow:
    """High-level workflow for prospecting research."""
    
    def __init__(
        self, 
        selling_product: SellingProduct,
        selling_product_research: str = "",
        model_name: str = "gemini-2.5-flash-preview-04-17",
        verbose: bool = True
    ):
        self.engine = ProspectingResearchEngine(
            selling_product=selling_product,
            model_name=model_name, 
            verbose=verbose,
            selling_product_research=selling_product_research
        )
        self.verbose = verbose
        self.selling_product = selling_product
        self.selling_product_research = selling_product_research
        
        # Default research steps
        self.research_steps = self._default_research_steps()
        
    def _calculate_signal_score(self, matched_signals: List[MatchedSignal], confirmed_signals: List[QualificationSignal]) -> float:
        """Calculate a score based on matched qualification signals."""
        if not matched_signals or not confirmed_signals:
            return 0.5  # Neutral score if no signals
        
        # Calculate total possible importance score
        total_possible_importance = sum(signal.importance for signal in confirmed_signals)
        if total_possible_importance == 0:
            return 0.5
        
        # Calculate actual matched importance score
        matched_importance = sum(signal.importance for signal in matched_signals)
        
        if self.verbose:
            print(f"Signal match calculation: {matched_importance}/{total_possible_importance} importance points")
            for signal in matched_signals:
                print(f"  + {signal.name}: +{signal.importance} points")
        
        # Calculate percentage of importance matched and convert to 0-1 scale
        signal_score = matched_importance / total_possible_importance
        
        # Apply some weighting to avoid extremes (minimum score of 0.3, scales up to 1.0)
        # This ensures even a single matched signal gives a reasonable score
        weighted_score = 0.3 + (signal_score * 0.7)
        
        # Ensure score is between 0 and 1 (though our formula guarantees this already)
        final_score = min(1.0, max(0.0, weighted_score))
        
        if self.verbose:
            print(f"Signal match score: {signal_score:.2f} → Weighted score: {final_score:.2f}")
        
        return final_score
    
    @staticmethod
    def _default_research_steps() -> List[ResearchStep]:
        """Default research steps for prospecting."""
        return [
            ResearchStep(
                step_id="company_overview",
                question="What does this company do? What are their main products and services?",
                prompt_template="""
                Provide a comprehensive overview of what this company does.
                Include:
                - Core products and services
                - Primary industry and sector
                - Target customers and markets
                - Company size and scale
                - Key value propositions
                
                Focus on factual information that would be relevant for B2B sales purposes.
                Be specific about what makes this company unique in their space.
                """
            ),
            ResearchStep(
                step_id="market_position",
                question="What is this company's position in the market? Who are their main competitors?",
                prompt_template="""
                Research this company's market position:
                - Market share if available
                - Main competitors (at least 3)
                - Competitive advantages and differentiators
                - Recent market developments affecting them
                - Growth trajectory
                
                Be specific about how they compare to competitors in terms of size, offerings, and approach.
                Focus on information that would help understand their competitive landscape.
                """,
                depends_on=["company_overview"]
            ),
            ResearchStep(
                step_id="tech_stack",
                question="What technologies does this company use? What is their technology stack?",
                prompt_template="""
                Research the technology stack and tools used by this company.
                Include:
                - Core platforms and infrastructure
                - Software applications and services
                - Development frameworks if relevant
                - Integration technologies
                - Digital presence technologies
                
                Be specific about the names of products they use when possible.
                Focus on technologies that might suggest integration opportunities or gaps.
                """,
                depends_on=["company_overview"]
            ),
            ResearchStep(
                step_id="pain_points",
                question="What potential business pain points and challenges might this company be facing?",
                prompt_template="""
                Based on your research, identify likely business pain points and challenges this company
                may be facing in their industry and business operations.
                
                Consider:
                - Industry-specific challenges
                - Operational inefficiencies they might have
                - Growth obstacles in their market
                - Technology gaps that might exist
                - Regulatory or compliance issues
                - Competitive pressures
                
                Ground your analysis in factual research about the company, their industry, and recent developments.
                Focus on pain points that would be relevant for B2B sales conversations.
                """,
                depends_on=["company_overview", "market_position", "tech_stack"]
            ),
            ResearchStep(
                step_id="recent_developments",
                question="What recent company developments, news, or changes have occurred in the past year?",
                prompt_template="""
                Research recent news, developments, and changes at the company in the past year.
                Look for:
                - Leadership changes
                - Funding or financial announcements
                - Product launches
                - Partnerships or acquisitions
                - Strategic initiatives
                - Expansion or contraction
                
                Include dates when available to establish a timeline of events.
                Focus on developments that suggest business priorities and direction.
                """,
                depends_on=["company_overview"]
            ),
            ResearchStep(
                step_id="product_fit",
                question="How well does our product fit with this company's needs? What is the potential value proposition?",
                prompt_template="""
                Based on all the previous research, analyze how well our product fits this target company's needs.
                
                OUR PRODUCT/SELLING COMPANY INFORMATION:
                
                PRODUCT RESEARCH:
                {selling_product_info}
                
                In your analysis, include:
                - Overall fit assessment (Excellent, Good, Moderate, Poor, Unsuitable)
                - Specific pain points our product could address
                - Key features that would be most valuable to them
                - Potential objections or obstacles to adoption
                - Customized value proposition for this specific company
                - Potential decision-makers or departments to approach
                
                IMPORTANT - QUALIFICATION SIGNAL ANALYSIS:
                Include a dedicated section titled "QUALIFICATION SIGNALS ANALYSIS" that contains:
                1. For EACH qualification signal listed above (whether matched or not):
                   - State whether the target company MATCHES or DOES NOT MATCH this signal
                   - If MATCHES: Provide specific evidence from your research supporting this match
                   - If DOES NOT MATCH: Briefly explain why not
                   - Consider the importance rating of each signal in your overall fit assessment
                
                2. Create a summary section titled "Matched Qualification Signals" that lists only the signals that match,
                   including their importance rating and a brief evidence statement for each.
                
                Be honest and objective in your assessment. If there isn't a good fit, explain why.
                If there is a good fit, be specific about which aspects of our product align with their needs.
                """,
                depends_on=["company_overview", "market_position", "tech_stack", "pain_points", "recent_developments"]
            )
        ]
    
    def set_research_steps(self, steps: List[ResearchStep]):
        """Set custom research steps."""
        self.research_steps = steps
    
    async def research_target(self, target: ProspectingTarget) -> ProspectingResult:
        """Execute the complete research workflow for a target company."""
        if self.verbose:
            print(f"\n=== Starting research for {target.company_name} ===\n")
        
        # Initialize research result
        result = ProspectingResult(
            target=target,
            selling_product=self.selling_product
        )
        
        # Execute steps in dependency order with overall timeout
        try:
            # Apply an overall timeout for the entire research process
            async with asyncio.timeout(TIMEOUTS["account_research"]):
                for step in self._get_steps_in_execution_order():
                    # Execute step with handling for step-specific timeouts
                    step_result = await self.engine.research_step(
                        target=target,
                        step=step,
                        previous_results={k: v for k, v in result.steps.items()}
                    )
                    
                    result.steps[step.step_id] = step_result
                    
                    if step_result.status in [ResearchStatus.FAILED, ResearchStatus.TIMEOUT]:
                        print(f"Step {step.step_id} {step_result.status}: {step_result.error}")
                        
                        # For dependent steps, we'll still continue but note the failure
                        if step_result.status == ResearchStatus.FAILED:
                            # Update answer to indicate failure when empty
                            if not step_result.answer:
                                step_result.answer = f"Research failed: {step_result.error}"
                
                # Extract key data from "product_fit" step
                await self._process_fit_assessment(result)
        
        except asyncio.TimeoutError:
            print(f"Overall research for {target.company_name} timed out after {TIMEOUTS['account_research']} seconds")
            result.overall_status = ResearchStatus.TIMEOUT
        
        # Mark research complete
        result.mark_completed()
        
        if self.verbose:
            print(f"\n=== Completed research for {target.company_name} ===\n")
        
        return result
    
    async def _process_fit_assessment(self, result: ProspectingResult):
        """Extract key data from the product_fit step results."""
        product_fit_step = result.steps.get("product_fit")
        
        if not product_fit_step or product_fit_step.status != ResearchStatus.COMPLETED:
            return
        
        # Process the fit assessment using AI
        try:
            # Include qualification signals in the analysis if available
            signals_section = ""
            if self.selling_product.qualification_signals:
                signals_section = "\nQUALIFICATION SIGNALS TO IDENTIFY IN THE ASSESSMENT:\n"
                for signal in self.selling_product.qualification_signals:
                    if signal.is_confirmed:
                        signals_section += f"- {signal.name}: {signal.description} (Importance: {signal.importance}/5)\n"
            
            fit_prompt = f"""
            Extract the key information from this product fit assessment into a structured format.
            
            ASSESSMENT: {product_fit_step.answer}
            {signals_section}
            
            Extract the following information in JSON format:
            - fit_level: The overall fit level (excellent, good, moderate, poor, unsuitable)
            - fit_score: A numerical score from 0.0 to 1.0 representing the fit
            - fit_explanation: A brief explanation of the fit assessment
            - pain_points: A list of pain points our product could address (5 max)
            - value_propositions: A list of value propositions tailored for this company (5 max)
            - objection_handling: A list of potential objections and responses (3 max)
            - key_decision_makers: A list of potential decision-makers or departments to approach
            - matched_signals: A list of objects representing qualification signals that match, each with:
              * name: The signal name
              * importance: A number 1-5 representing importance
              * evidence: Brief evidence from the assessment showing why this signal matches
            
            Return ONLY the formatted JSON.
            """
            
            response = await self.engine.llm.ainvoke(fit_prompt)
            content = response.content
            
            try:
                import re
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                extracted_json = json_match.group(1) if json_match else content
                
                # Parse the extracted JSON
                fit_data = repair_loads(extracted_json)
                
                # Update the result with extracted data
                result.fit_level = FitLevel(fit_data.get("fit_level", "unknown").lower())
                # Parse fit_score, ensuring it's a valid float
                try:
                    score_val = fit_data.get("fit_score")
                    if score_val is None:
                        # If no score was provided, derive from fit_level
                        level_scores = {
                            "excellent": 0.9,
                            "good": 0.7,
                            "moderate": 0.5,
                            "poor": 0.3,
                            "unsuitable": 0.1,
                            "unknown": 0.5
                        }
                        level = fit_data.get("fit_level", "unknown").lower()
                        result.fit_score = level_scores.get(level, 0.5)
                        if self.verbose:
                            print(f"No score provided, derived {result.fit_score} from level: {level}")
                    else:
                        # Try to convert to float, with fallback
                        try:
                            result.fit_score = float(score_val)
                        except (ValueError, TypeError):
                            # If conversion fails, derive from fit_level
                            level = fit_data.get("fit_level", "unknown").lower()
                            default_scores = {
                                "excellent": 0.9,
                                "good": 0.7,
                                "moderate": 0.5,
                                "poor": 0.3,
                                "unsuitable": 0.1,
                                "unknown": 0.5
                            }
                            result.fit_score = default_scores.get(level, 0.5)
                            if self.verbose:
                                print(f"Invalid score '{score_val}', using {result.fit_score} from level: {level}")
                except Exception as e:
                    # Default to moderate score if any errors
                    result.fit_score = 0.5
                    if self.verbose:
                        print(f"Error processing fit score: {e}, using default: 0.5")
                result.fit_explanation = fit_data.get("fit_explanation", "")
                result.pain_points = fit_data.get("pain_points", [])
                result.value_propositions = fit_data.get("value_propositions", [])
                result.objection_handling = fit_data.get("objection_handling", [])
                result.key_decision_makers = fit_data.get("key_decision_makers", [])
                
                # Process matched signals
                result.matched_signals = []
                if "matched_signals" in fit_data and isinstance(fit_data["matched_signals"], list):
                    for signal_data in fit_data["matched_signals"]:
                        if isinstance(signal_data, dict) and "name" in signal_data:
                            signal = MatchedSignal(
                                name=signal_data["name"],
                                importance=signal_data.get("importance", 5),
                                evidence=signal_data.get("evidence", "")
                            )
                            result.matched_signals.append(signal)
                        elif isinstance(signal_data, str):
                            # Handle simple string format for backward compatibility
                            # Try to find the original signal to get its importance
                            importance = 5
                            for orig_signal in self.selling_product.qualification_signals:
                                if orig_signal.name == signal_data:
                                    importance = orig_signal.importance
                                    break
                            signal = MatchedSignal(name=signal_data, importance=importance)
                            result.matched_signals.append(signal)
                
                # Log the raw fit score for debugging
                if self.verbose:
                    print(f"Raw fit score from assessment: {result.fit_score:.2f}")
                
                # Adjust fit score based on matched signals if there are confirmed signals
                confirmed_signals = [s for s in self.selling_product.qualification_signals if s.is_confirmed]
                if confirmed_signals and result.matched_signals:
                    signal_score_adjustment = self._calculate_signal_score(result.matched_signals, confirmed_signals)
                    # Blend original fit score (70%) with signal score (30%)
                    result.fit_score = (result.fit_score * 0.7) + (signal_score_adjustment * 0.3)
                    if self.verbose:
                        print(f"Signal score adjustment: {signal_score_adjustment:.2f}, Final adjusted score: {result.fit_score:.2f}")
                        print(f"Matched {len(result.matched_signals)} of {len(confirmed_signals)} qualification signals")
                else:
                    # If no signal matching, use the raw LLM score but make sure it's not 0
                    if result.fit_score == 0.0:
                        # Map fit level to default scores if the score is 0
                        default_scores = {
                            "excellent": 0.9,
                            "good": 0.7,
                            "moderate": 0.5,
                            "poor": 0.3,
                            "unsuitable": 0.1,
                            "unknown": 0.5
                        }
                        level = result.fit_level.value if isinstance(result.fit_level, Enum) else str(result.fit_level).lower()
                        result.fit_score = default_scores.get(level, 0.5)
                        if self.verbose:
                            print(f"Using default score based on fit level '{level}': {result.fit_score:.2f} (was 0.0)")
            
            except Exception as e:
                if self.verbose:
                    print(f"Error processing fit assessment: {str(e)}")
        
        except Exception as e:
            if self.verbose:
                print(f"Error extracting product fit data: {str(e)}")
    
    def _get_steps_in_execution_order(self) -> List[ResearchStep]:
        """Return steps ordered by dependencies."""
        # Simple topological sort
        result = []
        visited = set()
        
        def visit(step):
            if step.step_id in visited:
                return
            
            visited.add(step.step_id)
            
            # Visit dependencies first
            for dep_id in step.depends_on:
                for s in self.research_steps:
                    if s.step_id == dep_id:
                        visit(s)
            
            result.append(step)
        
        # Visit each step
        for step in self.research_steps:
            visit(step)
        
        return result
    
    def save_results(self, result: ProspectingResult, path: str = None):
        """Save research results to file."""
        if path is None:
            # Create filename from account name and timestamp
            filename = f"prospect_{result.target.company_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            path = filename
        
        with open(path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        if self.verbose:
            print(f"Results saved to {path}")


###############################
# Database Management
###############################

class DatabaseManager:
    """Manages database operations for storing and retrieving research results."""
    
    def __init__(self, db_path: str, use_duckdb: bool = True):
        """Initialize the database manager.
        
        Args:
            db_path: Path to the database file
            use_duckdb: Whether to use DuckDB (if available) or SQLite
        """
        self.db_path = db_path
        self.use_duckdb = use_duckdb and DUCKDB_AVAILABLE
        
        # Initialize database connection and tables
        self._init_db()
    
    def _init_db(self):
        """Initialize the database and create tables if they don't exist."""
        if self.use_duckdb:
            self.conn = duckdb.connect(self.db_path)
        else:
            self.conn = sqlite3.connect(self.db_path)
            
        # Create tables
        self._create_tables()
    
    def _create_tables(self):
        """Create necessary tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Create main research results table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_results (
            id TEXT PRIMARY KEY,
            company_name TEXT NOT NULL,
            website TEXT NOT NULL,
            industry TEXT,
            fit_level TEXT NOT NULL,
            fit_score REAL NOT NULL,
            fit_explanation TEXT,
            timestamp TEXT NOT NULL,
            selling_product_id TEXT NOT NULL,
            result_json TEXT NOT NULL
        )
        """)
        
        # Create selling products table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS selling_products (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            description TEXT,
            product_json TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """)
        
        # Create matched signals table (for easier querying by signal)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS matched_signals (
            id TEXT PRIMARY KEY,
            research_id TEXT NOT NULL,
            signal_name TEXT NOT NULL,
            importance INTEGER NOT NULL,
            evidence TEXT,
            FOREIGN KEY (research_id) REFERENCES research_results (id)
        )
        """)
        
        self.conn.commit()
    
    def save_selling_product(self, product: 'SellingProduct') -> str:
        """Save selling product to database and return its ID."""
        # Generate ID if not present
        product_id = str(uuid.uuid4())
        
        # Serialize product
        product_json = json.dumps(asdict(product))
        
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO selling_products (id, name, website, description, product_json, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            product.name,
            product.website,
            product.description,
            product_json,
            datetime.now().isoformat()
        ))
        
        self.conn.commit()
        return product_id
    
    def save_research_result(self, result: 'ProspectingResult', selling_product_id: str) -> str:
        """Save research result to database and return its ID."""
        # Generate ID if not present
        result_id = str(uuid.uuid4())
        
        # Serialize result
        result_json = json.dumps(result.to_dict())
        
        cursor = self.conn.cursor()
        cursor.execute("""
        INSERT INTO research_results (
            id, company_name, website, industry, fit_level, fit_score, 
            fit_explanation, timestamp, selling_product_id, result_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result_id,
            result.target.company_name,
            result.target.website,
            result.target.industry,
            result.fit_level.value if isinstance(result.fit_level, Enum) else result.fit_level,
            result.fit_score,
            result.fit_explanation,
            datetime.now().isoformat(),
            selling_product_id,
            result_json
        ))
        
        # Save matched signals for easier querying
        for signal in result.matched_signals:
            signal_id = str(uuid.uuid4())
            cursor.execute("""
            INSERT INTO matched_signals (id, research_id, signal_name, importance, evidence)
            VALUES (?, ?, ?, ?, ?)
            """, (
                signal_id,
                result_id,
                signal.name,
                signal.importance,
                signal.evidence
            ))
        
        self.conn.commit()
        return result_id
    
    def get_research_results(self, company_name: str = None, selling_product_id: str = None, 
                            min_fit_score: float = None, has_signal: str = None) -> List[Dict]:
        """Query research results with optional filters."""
        query = "SELECT id, company_name, website, industry, fit_level, fit_score, timestamp FROM research_results"
        params = []
        where_clauses = []
        
        if company_name:
            where_clauses.append("company_name LIKE ?")
            params.append(f"%{company_name}%")
        
        if selling_product_id:
            where_clauses.append("selling_product_id = ?")
            params.append(selling_product_id)
        
        if min_fit_score is not None:
            where_clauses.append("fit_score >= ?")
            params.append(min_fit_score)
        
        if has_signal:
            query = query.replace(
                "SELECT id", 
                "SELECT DISTINCT research_results.id"
            )
            query += " INNER JOIN matched_signals ON research_results.id = matched_signals.research_id"
            where_clauses.append("matched_signals.signal_name LIKE ?")
            params.append(f"%{has_signal}%")
        
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        
        # Order by fit score descending
        query += " ORDER BY fit_score DESC"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "company_name": row[1],
                "website": row[2],
                "industry": row[3],
                "fit_level": row[4],
                "fit_score": row[5],
                "timestamp": row[6]
            })
        
        return results
    
    def get_research_detail(self, research_id: str) -> Dict:
        """Get full details of a research result by ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT result_json FROM research_results WHERE id = ?",
            (research_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return json.loads(row[0])
    
    def get_signals_summary(self, selling_product_id: str = None) -> Dict[str, Dict]:
        """Get summary statistics for matched signals."""
        query = """
        SELECT 
            signal_name, 
            COUNT(*) as match_count, 
            AVG(importance) as avg_importance,
            MAX(importance) as max_importance
        FROM matched_signals
        """
        
        params = []
        if selling_product_id:
            query += """
            INNER JOIN research_results ON matched_signals.research_id = research_results.id
            WHERE research_results.selling_product_id = ?
            """
            params.append(selling_product_id)
        
        query += "GROUP BY signal_name ORDER BY match_count DESC, avg_importance DESC"
        
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        
        signals = {}
        for row in rows:
            signals[row[0]] = {
                "match_count": row[1],
                "avg_importance": row[2],
                "max_importance": row[3]
            }
        
        return signals
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()


###############################
# Data Loading and Utilities
###############################

def load_targets_from_csv(csv_file: str, limit: int = 0, offset: int = 0) -> List[ProspectingTarget]:
    """Load target companies from a CSV file.
    
    Args:
        csv_file: Path to the CSV file
        limit: Maximum number of targets to load (0 for all)
        offset: Number of targets to skip from the beginning
        
    Returns:
        List of ProspectingTarget objects
    """
    targets = []
    
    try:
        # Read the CSV file
        df = pd.read_csv(csv_file)
        
        required_columns = ["Company Name", "Website"]
        for col in required_columns:
            if col not in df.columns:
                raise ValueError(f"CSV file must contain '{col}' column")
        
        # Apply offset and limit if specified
        if offset > 0:
            if offset >= len(df):
                print(f"Warning: Offset {offset} exceeds the number of entries in the CSV ({len(df)})")
                return []
            df = df.iloc[offset:]
        
        if limit > 0:
            df = df.iloc[:limit]
            
        print(f"Processing {len(df)} companies from CSV (offset={offset}, limit={limit if limit > 0 else 'all'})")
        
        # Convert each row to a ProspectingTarget
        for _, row in df.iterrows():
            # Get optional columns if they exist
            industry = row.get("Industry", "") if "Industry" in df.columns else ""
            description = row.get("Description", "") if "Description" in df.columns else ""
            
            # Create additional_info dict with any extra columns
            additional_info = {}
            for col in df.columns:
                if col not in ["Company Name", "Website", "Industry", "Description"]:
                    additional_info[col] = row[col]
            
            # Create the target
            target = ProspectingTarget(
                company_name=row["Company Name"],
                website=row["Website"],
                industry=industry,
                description=description,
                additional_info=additional_info
            )
            
            targets.append(target)
    
    except Exception as e:
        print(f"Error loading targets from CSV: {str(e)}")
    
    return targets


def create_selling_product_from_input() -> SellingProduct:
    """Create a SellingProduct object from user input."""
    print("\n=== PRODUCT/COMPANY YOU'RE SELLING ===")
    name = input("Product/Company Name: ")
    website = input("Product/Company Website: ")
    
    # For the other fields, we'll automatically research them later
    return SellingProduct(
        name=name,
        website=website
    )


def create_sample_selling_product() -> SellingProduct:
    """Create a sample SellingProduct for testing."""
    return SellingProduct(
        name="Tessell",
        website="https://www.tessell.com"
    )


###############################
# Main Execution Functions
###############################

async def research_single_target(target: ProspectingTarget, product: SellingProduct, output_dir: str, db_manager: Optional[DatabaseManager] = None):
    """Research a single target company."""
    # Create research engine for selling product research
    engine = ProspectingResearchEngine(selling_product=product, verbose=True, selling_product_research="")
    
    # Research the selling product once
    selling_product_research = await research_selling_product(product, engine)
    
    # Create workflow with researched selling product
    workflow = ProspectingWorkflow(
        selling_product=product,
        selling_product_research=selling_product_research,
        verbose=True
    )
    
    # Run research
    result = await workflow.research_target(target)
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Save results
    output_path = os.path.join(
        output_dir, 
        f"prospect_{target.company_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    workflow.save_results(result, output_path)
    
    # Save to database if manager provided
    if db_manager:
        # Save selling product first if needed
        selling_product_id = db_manager.save_selling_product(product)
        # Save research result with reference to selling product
        research_id = db_manager.save_research_result(result, selling_product_id)
    
    # Print summary
    print("\nRESEARCH SUMMARY:")
    print(f"Target: {result.target.company_name}")
    print(f"Website: {result.target.website}")
    print(f"Fit Level: {result.fit_level}")
    print(f"Fit Score: {result.fit_score:.2f}")
    
    if result.matched_signals:
        print("\nMatched Qualification Signals:")
        for i, signal in enumerate(sorted(result.matched_signals, key=lambda x: x.importance, reverse=True), 1):
            print(f"  {i}. {signal.name} (Importance: {signal.importance}/5)")
            if signal.evidence:
                print(f"     Evidence: {signal.evidence}")
    
    if result.pain_points:
        print("\nTop Pain Points:")
        for i, pain in enumerate(result.pain_points[:3], 1):
            print(f"  {i}. {pain}")
    
    if result.value_propositions:
        print("\nKey Value Propositions:")
        for i, prop in enumerate(result.value_propositions[:3], 1):
            print(f"  {i}. {prop}")
    
    return result


async def research_selling_product(product: SellingProduct, engine: ProspectingResearchEngine) -> str:
    """Research the selling product once."""
    print(f"\n=== Researching Selling Product: {product.name} ===\n")
    
    try:
        # Create a research step for the selling product
        selling_product_step = ResearchStep(
            step_id="selling_product_research",
            question=f"Research our product '{product.name}' to understand its offerings, features, and value proposition.",
            prompt_template=f"""
            Research the product/company that we're selling to understand what it offers, its key features, value proposition, 
            and target market. This information will help us understand how it might fit with target companies' needs.
            
            PRODUCT/COMPANY TO RESEARCH:
            Name: {product.name}
            Website: {product.website}
            
            Provide a comprehensive overview including:
            1. What does this product/company do? What are its main offerings?
            2. What are the key features and capabilities?
            3. What is the primary value proposition?
            4. What industries or types of customers does it target?
            5. What problems does it solve for its customers?
            
            Focus on factual information that will be helpful for determining fit with target companies.
            """
        )
        
        # Create a dummy target to satisfy the research_step method
        dummy_target = ProspectingTarget(
            company_name=product.name,
            website=product.website
        )
        
        # Execute research for the selling product
        step_result = await engine.research_step(
            target=dummy_target,
            step=selling_product_step
        )
        
        if step_result.status != ResearchStatus.COMPLETED:
            print(f"Warning: Selling product research did not complete successfully: {step_result.status}")
            return f"Unable to complete research for {product.name}. Using basic information only."
        
        # Generate qualification signals from the research
        await identify_qualification_signals(product, step_result.answer, engine.llm)
        
        # Store the research in the engine for use in formatting prompts
        engine.selling_product_research = step_result.answer
        
        return step_result.answer
    
    except Exception as e:
        print(f"Error researching selling product: {str(e)}")
        return f"Error researching product: {str(e)}"


async def identify_qualification_signals(product: SellingProduct, research: str, llm, interactive: bool = True) -> List[QualificationSignal]:
    """Identify qualification signals from selling product research."""
    print("\n=== Identifying Qualification Signals ===\n")
    
    try:
        # Prompt to identify qualification signals
        signals_prompt = f"""
        Based on the research about {product.name}, identify the top 5 qualification signals that would indicate 
        a prospective customer is an ideal fit for this product. These signals should be specific, measurable 
        indicators that would help qualify a lead.
        
        PRODUCT RESEARCH:
        {research}
        
        For each signal:
        1. Provide a clear, concise name (e.g., "Uses Oracle Database")
        2. Write a brief description explaining why this signal matters
        3. Rate its importance on a scale of 1-5 (5 being most important), where:
           - 5: Critical signal - extremely strong indicator of fit
           - 4: Very important signal - strong indicator of fit
           - 3: Important signal - moderate indicator of fit
           - 2: Helpful signal - slight indicator of fit
           - 1: Minor signal - minimal indicator of fit
        4. Include brief instructions on how to detect this signal in prospective accounts
        
        Return your response as a JSON array with this structure:
        [
          {{
            "name": "Signal name",
            "description": "Why this matters",
            "importance": 5,
            "detection_instructions": "How to detect this signal"
          }},
          ...
        ]
        
        Focus on the most important, defining signals - the ones that truly separate ideal customers from poor fits.
        Be specific and precise in your signal definitions.
        """
        
        # Get signals from LLM
        response = await llm.ainvoke(signals_prompt)
        signals_text = response.content
        
        # Extract the JSON
        import re
        import json
        
        # Try to extract JSON from the response
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', signals_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = signals_text
        
        try:
            signals_data = json.loads(json_str)
        except:
            try:
                # Try to repair the JSON if it's malformed
                from json_repair import loads as repair_loads
                signals_data = repair_loads(json_str)
            except:
                print("Could not parse signals data. Using default signals.")
                return []
        
        # Convert to QualificationSignal objects
        signals = []
        for signal_data in signals_data:
            signal = QualificationSignal(
                name=signal_data["name"],
                description=signal_data["description"],
                importance=signal_data.get("importance", 5),
                detection_instructions=signal_data.get("detection_instructions", "")
            )
            signals.append(signal)
        
        # Limit to top 5 by importance
        signals.sort(key=lambda x: x.importance, reverse=True)
        signals = signals[:5]
        
        # Print signals
        print("Identified Qualification Signals:")
        for i, signal in enumerate(signals, 1):
            print(f"{i}. {signal.name}")
            print(f"   Description: {signal.description}")
            print(f"   Importance: {signal.importance}/5")
            print(f"   Detection: {signal.detection_instructions}")
            print()
        
        # Interactive confirmation
        confirmed_signals = []
        if interactive:
            print("\nPlease confirm each qualification signal or modify as needed:")
            for i, signal in enumerate(signals, 1):
                keep_signal = input(f"Keep signal #{i} '{signal.name}'? (y/n/e) [y=yes, n=no, e=edit]: ").lower()
                
                if keep_signal == 'y' or keep_signal == '':
                    signal.is_confirmed = True
                    confirmed_signals.append(signal)
                    print(f"Signal '{signal.name}' confirmed.")
                    
                elif keep_signal == 'e':
                    print(f"\nEditing signal '{signal.name}':")
                    new_name = input(f"New name (press Enter to keep '{signal.name}'): ")
                    new_desc = input(f"New description (press Enter to keep current): ")
                    new_imp = input(f"New importance (1-5, press Enter to keep {signal.importance}): ")
                    new_inst = input(f"New detection instructions (press Enter to keep current): ")
                    
                    if new_name.strip():
                        signal.name = new_name
                    if new_desc.strip():
                        signal.description = new_desc
                    if new_imp.strip() and new_imp.isdigit() and 1 <= int(new_imp) <= 5:
                        signal.importance = int(new_imp)
                    if new_inst.strip():
                        signal.detection_instructions = new_inst
                    
                    signal.is_confirmed = True
                    confirmed_signals.append(signal)
                    print(f"Edited signal added: {signal.name}")
                    
                else:
                    print(f"Signal '{signal.name}' skipped.")
            
            # Option to add a custom signal
            add_custom = input("\nAdd a custom qualification signal? (y/n): ").lower()
            if add_custom == 'y':
                name = input("Signal name: ")
                desc = input("Description: ")
                imp = input("Importance (1-5): ")
                inst = input("Detection instructions: ")
                
                importance = 5
                if imp.isdigit() and 1 <= int(imp) <= 5:
                    importance = int(imp)
                
                if name and desc:
                    custom_signal = QualificationSignal(
                        name=name,
                        description=desc,
                        importance=importance,
                        detection_instructions=inst,
                        is_confirmed=True
                    )
                    confirmed_signals.append(custom_signal)
                    print(f"Custom signal '{name}' added.")
        else:
            # Auto-confirm all signals in non-interactive mode
            for signal in signals:
                signal.is_confirmed = True
            confirmed_signals = signals
            
        # Update the product with the confirmed signals
        product.qualification_signals = confirmed_signals
        
        # Print final signals
        if confirmed_signals:
            print("\nFinal Qualification Signals:")
            for i, signal in enumerate(confirmed_signals, 1):
                print(f"{i}. {signal}")
        else:
            print("\nNo qualification signals confirmed.")
        
        return confirmed_signals
        
    except Exception as e:
        print(f"Error identifying qualification signals: {str(e)}")
        return []

async def batch_research_targets(targets: List[ProspectingTarget], product: SellingProduct, output_dir: str, limit: int = 0, db_manager: Optional[DatabaseManager] = None):
    """Research multiple target companies."""
    if limit > 0 and limit < len(targets):
        targets = targets[:limit]
        print(f"Limited to {limit} targets")
    
    print(f"Starting research for {len(targets)} targets")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create research engine for selling product research
    engine = ProspectingResearchEngine(selling_product=product, verbose=True, selling_product_research="")
    
    # Research the selling product once
    selling_product_research = await research_selling_product(product, engine)
    
    # Create workflow with researched selling product
    workflow = ProspectingWorkflow(
        selling_product=product,
        selling_product_research=selling_product_research,
        verbose=True
    )
    
    # Save selling product to database if manager provided
    selling_product_id = None
    if db_manager:
        selling_product_id = db_manager.save_selling_product(product)
    
    # Process each target
    results = []
    for i, target in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] Processing {target.company_name}")
        
        try:
            # Run research
            result = await workflow.research_target(target)
            
            # Save results
            output_path = os.path.join(
                output_dir, 
                f"prospect_{target.company_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            workflow.save_results(result, output_path)
            
            # Save to database if manager provided
            if db_manager and selling_product_id:
                db_manager.save_research_result(result, selling_product_id)
            
            # Add to results list
            results.append(result)
            
        except Exception as e:
            print(f"Error researching target {target.company_name}: {str(e)}")
    
    # Generate summary report
    generate_summary_report(results, product, os.path.join(output_dir, "summary_report.json"))
    
    # If database manager, generate signal analysis from DB
    if db_manager and selling_product_id:
        signals_summary = db_manager.get_signals_summary(selling_product_id)
        print("\nSignal Analysis from Database:")
        for signal_name, stats in signals_summary.items():
            print(f"  {signal_name}: {stats['match_count']} matches (Avg. Importance: {stats['avg_importance']:.1f}/5)")
    
    return results


def generate_summary_report(results: List[ProspectingResult], product: SellingProduct, output_path: str):
    """Generate a summary report of all research results."""
    if not results:
        print("No results to generate summary report")
        return
    
    summary = {
        "product": product.name,
        "total_targets": len(results),
        "timestamp": datetime.now().isoformat(),
        "qualification_signals": [
            {
                "name": signal.name,
                "description": signal.description,
                "importance": signal.importance
            }
            for signal in product.qualification_signals if signal.is_confirmed
        ],
        "targets_by_fit": {
            "excellent": [],
            "good": [],
            "moderate": [],
            "poor": [],
            "unsuitable": []
        },
        "targets": []
    }
    
    # Process each result
    for result in results:
        # Basic target info
        # Extract matched signals in a serializable way
        matched_signals_data = []
        for signal in result.matched_signals:
            matched_signals_data.append({
                "name": signal.name,
                "importance": signal.importance,
                "evidence": signal.evidence
            })
        
        target_summary = {
            "company_name": result.target.company_name,
            "website": result.target.website,
            "industry": result.target.industry,
            "fit_level": result.fit_level.value if isinstance(result.fit_level, Enum) else result.fit_level,
            "fit_score": result.fit_score,
            "matched_signals": matched_signals_data,
            "pain_points": result.pain_points[:3] if result.pain_points else [],
            "value_propositions": result.value_propositions[:2] if result.value_propositions else [],
            "key_decision_makers": result.key_decision_makers[:2] if result.key_decision_makers else [],
            "result_file": f"prospect_{result.target.company_name.replace(' ', '_').lower()}.json"
        }
        
        # Add to targets list
        summary["targets"].append(target_summary)
        
        # Add to fit level lists
        fit_level = result.fit_level.value if isinstance(result.fit_level, Enum) else result.fit_level
        if fit_level in summary["targets_by_fit"]:
            summary["targets_by_fit"][fit_level].append(result.target.company_name)
    
    # Sort targets by fit score (descending)
    summary["targets"].sort(key=lambda x: x["fit_score"], reverse=True)
    
    # Write to file
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary report written to {output_path}")
    
    # Print summary stats
    print("\n=== PROSPECTING SUMMARY ===")
    print(f"Total Targets: {len(results)}")
    
    for fit_level in ["excellent", "good", "moderate", "poor", "unsuitable"]:
        count = len(summary["targets_by_fit"][fit_level])
        print(f"{fit_level.capitalize()} Fit: {count} targets")
    
    # Count targets by qualification signals with importance
    signal_counts = {}
    total_importance = {}
    for target in summary["targets"]:
        for signal in target.get("matched_signals", []):
            signal_name = signal.get("name", "")
            importance = signal.get("importance", 5)
            if signal_name:
                signal_counts[signal_name] = signal_counts.get(signal_name, 0) + 1
                total_importance[signal_name] = total_importance.get(signal_name, 0) + importance
    
    if signal_counts:
        print("\nQualification Signal Matches:")
        # Sort by count first, then by importance if counts are tied
        for signal_name, count in sorted(signal_counts.items(), 
                                         key=lambda x: (x[1], total_importance.get(x[0], 0)), 
                                         reverse=True):
            avg_importance = total_importance[signal_name] / count if count > 0 else 0
            print(f"  {signal_name}: {count} targets (Avg. Importance: {avg_importance:.1f}/5)")
    
    if summary["targets"]:
        print("\nTop 3 Prospects:")
        for i, target in enumerate(summary["targets"][:3], 1):
            # Format matched signals with importance
            signals_text = ""
            if target.get("matched_signals"):
                # Sort by importance and take top 2
                top_signals = sorted(target["matched_signals"], key=lambda x: x.get("importance", 0), reverse=True)[:2]
                signal_strs = [f"{s['name']} ({s['importance']}/5)" for s in top_signals]
                signals_text = f" - Signals: {', '.join(signal_strs)}"
            
            print(f"  {i}. {target['company_name']} - Fit: {target['fit_level']} ({target['fit_score']:.2f}){signals_text}")


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Prospecting Research Tool")
    parser.add_argument("--csv", type=str, default="", help="Path to CSV file with target companies")
    parser.add_argument("--output", type=str, default="prospecting_results", help="Directory to save research results")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of targets to process from CSV (0 for all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many targets from the beginning of CSV")
    parser.add_argument("--sample-product", action="store_true", help="Use a sample product definition for testing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--db", type=str, default="prospecting.db", help="Database file path")
    parser.add_argument("--use-sqlite", action="store_true", help="Use SQLite instead of DuckDB (if available)")
    parser.add_argument("--query", action="store_true", help="Query mode - search existing results instead of running research")
    parser.add_argument("--company", type=str, default="", help="Filter by company name in query mode")
    parser.add_argument("--signal", type=str, default="", help="Filter by signal name in query mode")
    parser.add_argument("--min-score", type=float, default=None, help="Filter by minimum fit score in query mode")
    
    args = parser.parse_args()
    
    # Set up database manager
    db_manager = DatabaseManager(args.db, use_duckdb=not args.use_sqlite)
    
    # Query mode - search existing results
    if args.query:
        return run_query_mode(db_manager, args)
    
    # Research mode - run new research
    return run_research_mode(db_manager, args)


def run_query_mode(db_manager: DatabaseManager, args):
    """Query existing research results."""
    print("\n=== QUERY MODE ===")
    
    # Apply filters from arguments
    filters = {}
    if args.company:
        filters["company_name"] = args.company
    if args.signal:
        filters["has_signal"] = args.signal
    if args.min_score is not None:
        filters["min_fit_score"] = args.min_score
    
    # Report on filters being applied
    print("Filters applied:")
    if not filters:
        print("  None - showing all results")
    else:
        for k, v in filters.items():
            print(f"  {k}: {v}")
    
    # Run query
    results = db_manager.get_research_results(**filters)
    
    # Display results
    if not results:
        print("\nNo results match the specified filters.")
        return
    
    print(f"\nFound {len(results)} matching results:")
    for i, result in enumerate(results, 1):
        print(f"\n{i}. {result['company_name']}")
        print(f"   Website: {result['website']}")
        print(f"   Fit: {result['fit_level']} ({result['fit_score']:.2f})")
        print(f"   ID: {result['id']}")
    
    # Option to view details
    while True:
        detail_input = input("\nEnter result number to view details (or 'q' to quit): ")
        if detail_input.lower() == 'q':
            break
        
        try:
            idx = int(detail_input) - 1
            if 0 <= idx < len(results):
                result_id = results[idx]['id']
                full_result = db_manager.get_research_detail(result_id)
                
                # Display result details
                print(f"\n=== DETAILS FOR {full_result['target']['company_name']} ===")
                print(f"Fit Level: {full_result['fit_level']}")
                print(f"Fit Score: {full_result['fit_score']:.2f}")
                print(f"Fit Explanation: {full_result['fit_explanation']}")
                
                # Display matched signals
                if "matched_signals" in full_result and full_result["matched_signals"]:
                    print("\nMatched Qualification Signals:")
                    for i, signal in enumerate(full_result["matched_signals"], 1):
                        print(f"  {i}. {signal['name']} (Importance: {signal['importance']}/5)")
                        if "evidence" in signal and signal["evidence"]:
                            print(f"     Evidence: {signal['evidence']}")
                
                # Display pain points and value propositions
                if "pain_points" in full_result and full_result["pain_points"]:
                    print("\nPain Points:")
                    for i, point in enumerate(full_result["pain_points"], 1):
                        print(f"  {i}. {point}")
                
                if "value_propositions" in full_result and full_result["value_propositions"]:
                    print("\nValue Propositions:")
                    for i, prop in enumerate(full_result["value_propositions"], 1):
                        print(f"  {i}. {prop}")
            else:
                print("Invalid result number. Please try again.")
                
        except ValueError:
            print("Invalid input. Please enter a number or 'q'.")
    
    # Close database connection
    db_manager.close()


def run_research_mode(db_manager: DatabaseManager, args):
    """Run research on new targets."""
    # Check for required environment variables
    missing_vars = []
    for var in ["GEMINI_API_TOKEN", "JINA_API_TOKEN"]:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"Missing required environment variables: {', '.join(missing_vars)}")
        print("\nPlease set them before running the script:")
        for var in missing_vars:
            print(f"export {var}=your_token_here")
        return
    
    # Get selling product
    if args.sample_product:
        product = create_sample_selling_product()
        print(f"Using sample product: {product.name}")
    else:
        product = create_selling_product_from_input()
    
    # Get target companies
    targets = []
    if args.csv:
        # Add additional arguments for CSV processing
        csv_offset = args.offset if hasattr(args, 'offset') and args.offset > 0 else 0
        csv_limit = args.limit if hasattr(args, 'limit') and args.limit > 0 else 0
        
        targets = load_targets_from_csv(args.csv, limit=csv_limit, offset=csv_offset)
        
        if csv_offset > 0 or csv_limit > 0:
            print(f"Loaded {len(targets)} targets from {args.csv} (offset={csv_offset}, limit={csv_limit if csv_limit > 0 else 'all'})")
        else:
            print(f"Loaded {len(targets)} targets from {args.csv}")
    else:
        # Create a sample target if no CSV provided
        print("\n=== TARGET COMPANY ===")
        company_name = input("Company Name: ")
        website = input("Website: ")
        industry = input("Industry (optional): ")
        
        targets = [ProspectingTarget(
            company_name=company_name,
            website=website,
            industry=industry
        )]
    
    # Run research
    try:
        if len(targets) == 1:
            asyncio.run(research_single_target(targets[0], product, args.output, db_manager))
        else:
            asyncio.run(batch_research_targets(targets, product, args.output, args.limit, db_manager))
    finally:
        # Always close database connection
        db_manager.close()


if __name__ == "__main__":
    main()
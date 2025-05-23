#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Core research engine for deep prospecting analysis.
Handles the execution of research steps and validation.
"""

import os
import asyncio
import re
from typing import Dict, Any, List, Optional

# clean_jina module is imported at the module level in main.py
# which sets up environment variables and logging configuration before any imports
# JinaSearch is imported directly from langchain_community.tools.jina_search

# LangChain imports
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain_community.tools import DuckDuckGoSearchRun
# Import JinaSearch directly from langchain_community
from langchain_community.tools.jina_search import JinaSearch
from langchain_community.utilities.jina_search import JinaSearchAPIWrapper
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

# Import AgentExecutor (removed custom executor)

from .data_models import (
    SellingProduct, ProspectingTarget, ResearchStepResult, 
    ResearchStatus, ConfidenceLevel, ResearchStep
)
from .config import TIMEOUTS

try:
    from json_repair import loads as repair_loads
except ImportError:
    import json
    repair_loads = json.loads


class ProspectingResearchEngine:
    """Engine for performing deep research on prospective accounts."""
    
    def __init__(
        self, 
        selling_product: SellingProduct,
        model_name: str = "gemini-2.5-flash-preview-05-20",
        pro_model_name: str = "gemini-2.5-pro-preview-05-06",
        verbose: bool = True,
        selling_product_research: str = "",
        enable_validation: bool = False,
        disable_tool_output: bool = True
    ):
        self.verbose = verbose
        self.model_name = model_name
        self.selling_product = selling_product
        self.enable_validation = enable_validation
        self.selling_product_research = selling_product_research
        self.disable_tool_output = disable_tool_output
        
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
            self.pro_llm = ChatGoogleGenerativeAI(
                model=pro_model_name,
                temperature=0.2,
                google_api_key=google_api_key
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")
        
        # Set up search tools
        self.search_tools = self._setup_search_tools()
        self.specialized_tools = self._setup_specialized_tools()
        
        # Set up research agents
        self.research_agent = self._create_research_agent()
        self.validation_agent = self._create_validation_agent()
    
    def _setup_search_tools(self) -> List[BaseTool]:
        """Set up search tools for research and validation."""
        tools = []

        # Set up search tools
        # Try to use Jina if available, otherwise use DuckDuckGo
        try:
            # Make sure the environment variables are properly mapped
            if "JINA_API_TOKEN" in os.environ and "JINA_API_KEY" not in os.environ:
                os.environ["JINA_API_KEY"] = os.environ["JINA_API_TOKEN"]
                
            # Use JINA_API_KEY which is what the wrapper expects
            jina_api_key = os.getenv("JINA_API_KEY")
            if jina_api_key:
                # Create standard wrapper without passing api_key explicitly
                # This makes it use JINA_API_KEY from environment
                wrapper = JinaSearchAPIWrapper()
                
                # Use the standard JinaSearch from langchain_community
                jina_tool = JinaSearch(api_wrapper=wrapper)
                tools.append(jina_tool)
            else:
                # Fallback to DuckDuckGo (already added below)
                pass
        except Exception as e:
            if self.verbose:
                print(f"Error setting up Jina search: {e}")
            # Will fall back to DuckDuckGo

        # Set up DuckDuckGo as fallback
        ddg_tool = DuckDuckGoSearchRun()
        ddg_tool.name = "duckduckgo_search"
        ddg_tool.description = """FALLBACK TOOL: **Use only if Jina doesn't find information**.
        Good for general verification but less reliable for exact numbers."""
        tools.append(ddg_tool)

        return tools
    
    def _setup_specialized_tools(self) -> List[BaseTool]:
        """Set up specialized tools like BuiltWith and Apollo."""
        try:
            from .specialized_tools import create_specialized_tools
            apollo_key = os.getenv("APOLLO_API_KEY")
            specialized_tools = create_specialized_tools(apollo_api_key=apollo_key)
            if self.verbose:
                print(f"Initialized {len(specialized_tools)} specialized tools")
            return specialized_tools
        except ImportError as e:
            if self.verbose:
                print(f"Could not import specialized tools: {e}")
            return []
        except Exception as e:
            if self.verbose:
                print(f"Error setting up specialized tools: {e}")
            return []
    
    def _create_agent_for_step(self, step: ResearchStep) -> AgentExecutor:
        """Create an agent with appropriate tools for a specific research step."""
        # Determine which tools to use based on step
        tools = list(self.search_tools)  # Always include search tools
        
        # Add specialized tools based on step flags
        if hasattr(step, 'use_builtwith') and step.use_builtwith:
            for tool in self.specialized_tools:
                if tool.name == "builtwith_technology":
                    tools.append(tool)
                    if self.verbose:
                        print(f"Added BuiltWith tool for step {step.step_id}")
        
        if hasattr(step, 'use_apollo') and step.use_apollo:
            for tool in self.specialized_tools:
                if tool.name == "apollo_company_profile":
                    tools.append(tool)
                    if self.verbose:
                        print(f"Added Apollo tool for step {step.step_id}")
        
        # Create agent with the selected tools
        system_prompt = f"""You are an expert B2B sales and account research specialist.
        Your task is to research companies to identify sales opportunities, pain points, and fit with a product.
        
        CURRENT RESEARCH TASK: {step.question}
        
        AVAILABLE TOOLS:
        {', '.join([f'{tool.name}: {tool.description}' for tool in tools])}
        
        RESEARCH PROCESS:
        1. Understand the research question clearly
        2. Use the most appropriate tools for the task
        3. For technology research, prioritize BuiltWith if available
        4. For company profiles, prioritize Apollo if available
        5. Complement with web search for additional context
        6. Synthesize findings into a comprehensive answer
        
        Be thorough but CONCISE - focus on the most valuable insights.
        """
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(self.llm, tools, prompt)
        memory = ConversationBufferMemory(return_messages=True, memory_key="chat_history")
        
        # Import our custom callback handler if blue tool output is disabled
        if self.disable_tool_output:
            from .custom_callbacks import SilentToolCallbackHandler
            callbacks = [SilentToolCallbackHandler()]
        else:
            callbacks = None
            
        return AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=self.verbose,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=TIMEOUTS["agent_max_iterations"],
            max_execution_time=TIMEOUTS["agent_execution_time"],
            callbacks=callbacks
        )
    
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
        - Be thorough but CONCISE in your research - focus on the most valuable insights
        - Focus on factual, verifiable information
        - Pay attention to recency - prefer newer information
        - Cite sources by linking to them
        - Think step-by-step and document your reasoning
        - Focus on B2B sales-relevant information
        - Look for business pain points and opportunities
        - Do NOT extrapolate or speculate - stick to the facts and base your conclusions on evidence
        
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

        # Import our custom callback handler if blue tool output is disabled
        if self.disable_tool_output:
            from .custom_callbacks import SilentToolCallbackHandler
            callbacks = [SilentToolCallbackHandler()]
        else:
            callbacks = None

        return AgentExecutor(
            agent=agent,
            tools=self.search_tools,
            verbose=self.verbose,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=TIMEOUTS["agent_max_iterations"],
            max_execution_time=TIMEOUTS["agent_execution_time"],
            callbacks=callbacks
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

        # Import our custom callback handler if blue tool output is disabled
        if self.disable_tool_output:
            from .custom_callbacks import SilentToolCallbackHandler
            callbacks = [SilentToolCallbackHandler()]
        else:
            callbacks = None
            
        return AgentExecutor(
            agent=agent,
            tools=self.search_tools,
            verbose=self.verbose,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=TIMEOUTS["agent_max_iterations"],
            max_execution_time=TIMEOUTS["agent_execution_time"],
            callbacks=callbacks
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
            
            # Create an agent with appropriate tools for this step
            agent = self._create_agent_for_step(step)
            
            # Execute research with timeout
            try:
                agent_result = await asyncio.wait_for(
                    agent.ainvoke({"input": research_prompt}),
                    timeout=TIMEOUTS["research_step"]
                )
                answer = agent_result.get("output", "")
                
                result = ResearchStepResult(
                    step_id=step.step_id,
                    question=step.question,
                    answer=answer,
                    status=ResearchStatus.COMPLETED,
                    confidence=0.5,  # Initial confidence before validation
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
            if self.enable_validation or step.validate_with_search:
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
            previous_research = "PREVIOUS RESEARCH FINDINGS:\\n"
            for step_id, answer in context.items():
                previous_research += f"- {step_id}: {answer}\\n"
        
        # Process template to handle special placeholders
        template = step.prompt_template
        
        # Replace {selling_product_info} with the actual selling product research
        if "{selling_product_info}" in template:
            # Include qualification signals if available
            qualification_signals_text = ""
            if self.selling_product.qualification_signals:
                qualification_signals_text = "\\nQUALIFICATION SIGNALS TO CHECK FOR:\\n"
                for signal in self.selling_product.qualification_signals:
                    if signal.is_confirmed:
                        qualification_signals_text += f"- {signal.name} (Importance: {signal.importance}/5)\\n  Description: {signal.description}\\n  Detection Instructions: {signal.detection_instructions}\\n"
            
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
        """Validate a research result using search with enhanced confidence scoring."""
        try:
            if self.verbose:
                print(f"\\n--- Validating {step.step_id} for {target.company_name} ---")
                
            validation_prompt = f"""
            Validate this sales research answer using multiple sources:
            
            QUESTION: <question> {step.question} </question>
            
            CLAIMED ANSWER(NEED TO VALIDATE): <answer> {result.answer} </answer>
            
            COMPANY INFORMATION: <context> 
            - Name: {target.company_name}
            - Website: {target.website}
            - Industry: {target.industry if target.industry else "Unknown"}
            </context>
            
            VALIDATION INSTRUCTIONS:
            1. IDENTIFY CRITICAL CLAIMS: List 3-5 critical claims that need verification
            2. SEARCH MULTIPLE SOURCES: Verify each claim using at least 2 different sources
            3. CHECK FOR CONFLICTS: Identify any conflicting information between sources
            4. ASSESS SOURCE QUALITY: Rate the reliability of each source (official company info, news outlets, industry reports)
            5. CALCULATE CONFIDENCE: Provide a confidence score (0.0-1.0) based on:
               - Number of confirming sources
               - Quality of sources
               - Presence of conflicting information
               - Recency of information
               
            FORMAT YOUR RESPONSE AS:
            - VERIFIED CLAIMS: [List of verified claims with supporting sources]
            - CONFLICTS FOUND: [Any conflicting information discovered]
            - SOURCE QUALITY: [Assessment of source reliability]
            - CONFIDENCE SCORE: [0.0-1.0]
            - UPDATED ANSWER: [Corrected answer if changes needed, or "No changes needed"]
            
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
            conflicts = validation_result.get("conflicts_found", [])
            source_quality = validation_result.get("source_quality", "Unknown")
            
            updated_result = ResearchStepResult(
                step_id=result.step_id,
                question=result.question,
                answer=validation_result.get("corrected_answer", result.answer) if validation_result.get("validation_status") == "validated_incorrect" else result.answer,
                status=result.status,
                validation_status=validation_result.get("validation_status"),
                validation_notes=validation_result.get("validation_notes"),
                conflict_notes="; ".join(conflicts) if conflicts else None,
                source_quality=source_quality,
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
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
            
            if json_match:
                json_str = json_match.group(1)
                return repair_loads(json_str)
            
            # If no JSON block found, try to repair the entire text
            return repair_loads(text)
        except Exception as e:
            print(f"Error parsing JSON response: {str(e)}")
            return {}
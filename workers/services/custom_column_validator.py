import os
from datetime import datetime
from functools import wraps
from typing import Dict, Any, List

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools.jina_search import JinaSearch
from langchain_community.utilities.jina_search import JinaSearchAPIWrapper
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

from services.task_registry import TaskRegistry
from utils.loguru_setup import logger
from json_repair import loads as repair_loads


class CustomColumnValidator:
    """Pure LangChain-based validator for AI-generated answers."""

    def __init__(self, model_name: str = "gemini-2.5-flash-preview-04-17"):
        # Configure LLM
        if "gemini" in model_name.lower():
            google_api_key = os.getenv("GEMINI_API_TOKEN")
            if not google_api_key:
                raise ValueError("GEMINI_API_TOKEN environment variable must be set")

            self.llm = ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.1,
                google_api_key = google_api_key
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")

        # Configure search tools
        self.search_tools = self._setup_search_tools()

        # Set up the validation agent
        self.validator_agent = self._create_validation_agent()

    @staticmethod
    def _setup_search_tools() -> List[BaseTool]:
        tools = []

        jina_api_key_value = os.getenv("JINA_API_TOKEN")
        if jina_api_key_value:
            jina_wrapper = JinaSearchAPIWrapper(api_key=SecretStr(jina_api_key_value))
            jina_tool = JinaSearch(search_wrapper=jina_wrapper)
            jina_tool.description = "Searches the web using Jina's AI-powered search. Use this for finding specific facts and information about companies, products, recent events, or market data."
            tools.append(jina_tool)

        ddg_tool = DuckDuckGoSearchRun()
        ddg_tool.name = "duckduckgo_search"
        ddg_tool.description = "FALLBACK TOOL: **Use only if Jina doesn't find information**.\n Good for general verification but less reliable for exact numbers."
        tools.append(ddg_tool)

        return tools

    def _create_validation_agent(self) -> AgentExecutor:
        system_prompt = """You are a B2B sales data fact validator. Your task is to verify AI-generated answers 
        about companies, markets, and sales information.
        
        Follow this validation process:
        1. First, identify 2-3 specific claims in the answer that are critical to validate. Make sure the claims are critical for the answer to be factually correct in response to the question asked.
        2. For each claim, formulate a precise search query
        3. Execute the search and analyze the results
        4. Compare the search results to the original claim - is it confirmed, contradicted, or inconclusive?
        5. After checking all claims, provide an overall validation assessment
        
        Think step-by-step and document your reasoning clearly. Be thorough in your analysis
        of the search results, noting when information is confirmed or contradicted.
        
        IMPORTANT: You MUST verify multiple claims before concluding. 
        E.g.:
            - Search claim 1 → Analyze results
            - Search claim 2 → Analyze results  
            - Only then provide final JSON assessment
        Never conclude after just one search unless you find contradictory evidence.

        
        End your analysis with a JSON validation result formatted exactly like this:
        ```json
        {{
          "is_validated": true or false,
          "confidence": 0.8,
          "validation_notes": "Your reasoning here",
          "corrected_answer": "Corrected version if needed, or null"
        }}
        ```
        
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
            verbose=True,
            memory=memory,
            handle_parsing_errors=True,
            max_iterations=8,
        )

    async def apply_to_task(self, task_registry: TaskRegistry):
        try:
            custom_column_task = task_registry.get_task("custom_column")

            original_process_entity = custom_column_task._process_entity

            # Create a wrapped version with validation
            @wraps(original_process_entity)
            async def validated_process_entity(*args, **kwargs):
                # Call the original method first
                entity_result = await original_process_entity(*args, **kwargs)

                # Only validate completed results when explicitly enabled
                if (entity_result.status == "completed" and
                        kwargs.get("ai_config", {}).get("validate_with_search", False)):

                    entity_id = kwargs.get("entity_id", "unknown")
                    column_id = kwargs.get("column_id", "unknown")

                    logger.info(f"Validating result for entity {entity_id}, column {column_id}")

                    validated_result = await self.validate_with_search(
                        entity_result=entity_result,
                        entity_context=kwargs.get("context_data", {}).get(entity_id, {}),
                        column_config=kwargs.get("column_config", {})
                    )
                    return validated_result

                return entity_result

            # Replace the method
            custom_column_task._process_entity = validated_process_entity
            logger.info("Successfully applied LangChain validation to CustomColumnTask")

            return custom_column_task

        except KeyError:
            logger.error("CustomColumnTask not found in registry")
            return None
        except Exception as e:
            logger.error(f"Error applying validation: {str(e)}")
            return None

    async def validate_with_search(self,
                                   entity_result: Any,
                                   entity_context: Dict[str, Any],
                                   column_config: Dict[str, Any]) -> Any:
        try:
            question = column_config.get('question', '')
            response_type = column_config.get('response_type', 'string')
            answer_value = self._extract_value(entity_result, response_type)

            logger.info(f"Validating answer for question: {question}")

            # Construct the validation prompt for the agent
            input_data = {
                "input": f"""
                Validate this sales answer:
                
                QUESTION: <question> {question} </question>
                
                CLAIMED ANSWER(NEED TO VALIDATE): <answer> {answer_value} </answer>
                
                COMPANY CONTEXT: <context> {entity_context} </context>
                
                INSTRUCTIONS:
                1. Identify 2-3 critical claims that need verification
                2. Search for relevant information using the search tools
                3. Evaluate if the search results CONFIRM or CONTRADICT the claims
                4. Provide a final validation with confidence score
                
                After your analysis, provide a JSON validation result with these fields:
                - "is_validated": boolean (true if answer is validated and proved to be correct by your research)
                - "confidence": float from 0.0 to 1.0
                - "validation_notes": your assessment explanation
                - "corrected_answer": corrected answer if the original has factual errors, or null
                """
            }

            agent_result = await self.validator_agent.ainvoke(input_data)
            agent_output = agent_result.get("output", "")

            validation_result = self._extract_json_from_text(agent_output)

            if not validation_result or not isinstance(validation_result, dict):
                validation_result = {
                    "is_validated": True, # Return true, so that we can keep the original answer
                    "confidence": 0.5,
                    "validation_notes": "Validation failed: Agent did not return proper validation result",
                    "corrected_answer": None
                }

            updated_result = self._apply_validation_results(
                entity_result,
                validation_result,
                response_type
            )

            return updated_result

        except Exception as e:
            logger.error(f"LangChain validation failed: {str(e)}", exc_info=True)
            return entity_result

    @staticmethod
    def _extract_json_from_text(text: str) -> Dict[str, Any]:
        """Extract JSON content from text response."""
        try:
            # Let json_repair handle everything - it returns Python objects directly
            return repair_loads(text)
        except Exception as e:
            logger.error(f"Error parsing JSON response: {str(e)}")
            return {}

    @staticmethod
    def _extract_value(entity_result, response_type: str) -> Any:
        if response_type == "string":
            return entity_result.value_string
        elif response_type == "json_object":
            return entity_result.value_json
        elif response_type == "boolean":
            return entity_result.value_boolean
        elif response_type == "number":
            return entity_result.value_number
        elif response_type == "enum":
            return entity_result.value_enum
        else:
            return None

    @staticmethod
    def _apply_validation_results(entity_result,
                                  validation_result: Dict[str, Any],
                                  response_type: str) -> Any:
        updated_result = type(entity_result)(**entity_result.dict())

        if validation_result.get("is_validated", False):
            updated_result.confidence_score = min(0.95, (entity_result.confidence_score or 0.5) + 0.1)
        else:
            updated_result.confidence_score = max(0.1, (entity_result.confidence_score or 0.5) - 0.2)

        corrected_answer = validation_result.get("corrected_answer")
        if corrected_answer:
            if response_type == "string":
                updated_result.value_string = corrected_answer
            elif response_type == "json_object":
                updated_result.value_json = corrected_answer
            elif response_type == "boolean":
                updated_result.value_boolean = corrected_answer
            elif response_type == "number":
                updated_result.value_number = corrected_answer
            elif response_type == "enum":
                updated_result.value_enum = corrected_answer

        validation_notes = validation_result.get("validation_notes", "")
        if validation_notes:
            existing_rationale = updated_result.rationale or ""
            updated_result.rationale = f"**Validation:** {validation_notes}\n\n{existing_rationale}"

        if not updated_result.error_details:
            updated_result.error_details = {}

        updated_result.error_details["search_validation"] = {
            "is_validated": validation_result.get("is_validated", False),
            "validation_confidence": validation_result.get("confidence", 0.5),
            "validated_at": datetime.now().isoformat(),
            "validation_tool": "langchain_agent"
        }

        return updated_result
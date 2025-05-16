#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Workflow management for deep prospecting research.
Orchestrates the research steps and processes results.
"""

import os
import json
import asyncio
import re
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime

from .data_models import (
    SellingProduct, ProspectingTarget, ProspectingResult, ResearchStep,
    ResearchStatus, ResearchStepResult, MatchedSignal, FitLevel, QualificationSignal
)
from .research_engine import ProspectingResearchEngine
from .config import TIMEOUTS, FIT_LEVEL_SCORES, SIGNAL_WEIGHT, BASE_SCORE_WEIGHT, MAX_QUALIFICATION_SIGNALS

try:
    from json_repair import loads as repair_loads
except ImportError:
    import json
    repair_loads = json.loads


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
    
    async def identify_qualification_signals(self, product: SellingProduct, research: str, interactive: bool = False) -> List[QualificationSignal]:
        """
        Identify qualification signals from selling product research.
        By default, runs in automatic mode (interactive=False) with no user input required.
        """
        print("\n=== Identifying Qualification Signals ===\n")
        
        try:
            # Prompt to identify qualification signals
            signals_prompt = f"""
            Based on the research about {product.name}, identify the top {MAX_QUALIFICATION_SIGNALS} qualification signals that would indicate 
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
            response = await self.engine.llm.ainvoke(signals_prompt)
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
            
            # Generate fallback signals in case parsing fails
            fallback_signals = [
                {
                    "name": "Large enterprise customer",
                    "description": "Companies with significant resources and budgets are more likely to adopt our solution.",
                    "importance": 4,
                    "detection_instructions": "Look for companies with 1000+ employees or significant revenue."
                },
                {
                    "name": "Uses complementary technologies",
                    "description": "Companies using technologies that work well with our product are better targets.",
                    "importance": 5,
                    "detection_instructions": "Check company tech stack for complementary technologies."
                },
                {
                    "name": "Growing rapidly",
                    "description": "Fast-growing companies often need our solution to scale their operations.",
                    "importance": 3,
                    "detection_instructions": "Look for recent funding, expansion news, or hiring sprees."
                }
            ]
            
            # Parse JSON or use fallback
            try:
                signals_data = json.loads(json_str)
            except:
                try:
                    # Try to repair the JSON if it's malformed
                    signals_data = repair_loads(json_str)
                except:
                    print("Could not parse signals data. Using fallback signals.")
                    signals_data = fallback_signals
            
            # Limit to MAX_QUALIFICATION_SIGNALS
            if len(signals_data) > MAX_QUALIFICATION_SIGNALS:
                # Sort by importance first
                signals_data = sorted(signals_data, key=lambda x: x.get('importance', 0), reverse=True)
                signals_data = signals_data[:MAX_QUALIFICATION_SIGNALS]
                print(f"Limited to top {MAX_QUALIFICATION_SIGNALS} signals by importance")
            
            # Convert to QualificationSignal objects
            signals = []
            for signal_data in signals_data:
                signal = QualificationSignal(
                    name=signal_data["name"],
                    description=signal_data["description"],
                    importance=signal_data.get("importance", 5),
                    detection_instructions=signal_data.get("detection_instructions", ""),
                    is_confirmed=not interactive  # Auto-confirm in non-interactive mode
                )
                signals.append(signal)
            
            # Print signals
            print("Identified Qualification Signals:")
            for i, signal in enumerate(signals, 1):
                print(f"{i}. {signal.name}")
                print(f"   Description: {signal.description}")
                print(f"   Importance: {signal.importance}/5")
                print(f"   Detection: {signal.detection_instructions}")
                print()
            
            # Interactive confirmation if requested
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
                # In automatic mode, all signals are already confirmed
                confirmed_signals = signals
                print(f"Auto-confirmed {len(signals)} qualification signals in non-interactive mode.")
                
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
            # Generate fallback signals if there was an error
            fallback_signals = [
                QualificationSignal(
                    name="Large enterprise customer",
                    description="Companies with significant resources and budgets are more likely to adopt our solution.",
                    importance=4,
                    detection_instructions="Look for companies with 1000+ employees or significant revenue.",
                    is_confirmed=True
                ),
                QualificationSignal(
                    name="Uses complementary technologies",
                    description="Companies using technologies that work well with our product are better targets.",
                    importance=5,
                    detection_instructions="Check company tech stack for complementary technologies.",
                    is_confirmed=True
                ),
                QualificationSignal(
                    name="Growing rapidly",
                    description="Fast-growing companies often need our solution to scale their operations.",
                    importance=3,
                    detection_instructions="Look for recent funding, expansion news, or hiring sprees.",
                    is_confirmed=True
                )
            ]
            
            print("Using fallback qualification signals due to error.")
            product.qualification_signals = fallback_signals[:MAX_QUALIFICATION_SIGNALS]
            return fallback_signals[:MAX_QUALIFICATION_SIGNALS]
        
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
        """Default research steps for streamlined prospecting."""
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
            # Removed market_position step
            # Removed tech_stack step
            # ResearchStep(
            #     step_id="pain_points",
            #     question="What potential business pain points and challenges might this company be facing?",
            #     prompt_template="""
            #     Based on your research, identify likely business pain points and challenges this company
            #     may be facing in their industry and business operations.
            #
            #     Consider:
            #     - Industry-specific challenges
            #     - Operational inefficiencies they might have
            #     - Growth obstacles in their market
            #     - Technology gaps that might exist
            #     - Regulatory or compliance issues
            #     - Competitive pressures
            #
            #     Ground your analysis in factual research about the company, their industry, and recent developments.
            #     Focus on pain points that would be relevant for B2B sales conversations.
            #     """,
            #     depends_on=["company_overview"]
            # ),
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
                depends_on=["company_overview", "pain_points", "recent_developments"]
            )
        ]
    
    def set_research_steps(self, steps: List[ResearchStep]):
        self.research_steps = steps
    
    async def research_target(self, target: ProspectingTarget) -> ProspectingResult:
        """Execute the complete research workflow for a target company."""
        start_time = time.time()
        
        if self.verbose:
            print(f"\\n=== Starting research for {target.company_name} at {datetime.now().strftime('%H:%M:%S')} ===\\n")
        
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
                    step_start_time = time.time()
                    
                    # Execute step with handling for step-specific timeouts
                    step_result = await self.engine.research_step(
                        target=target,
                        step=step,
                        previous_results={k: v for k, v in result.steps.items()}
                    )
                    
                    step_duration = time.time() - step_start_time
                    if self.verbose:
                        print(f"Step {step.step_id} completed in {step_duration:.1f} seconds")
                    
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
        
        # Mark research complete and calculate time
        end_time = time.time()
        total_duration = end_time - start_time
        result.mark_completed(start_time)
        result.total_time_seconds = total_duration
        
        if self.verbose:
            print(f"\\n=== Completed research for {target.company_name} in {total_duration:.1f} seconds ===\\n")
        
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
                signals_section = "\\nQUALIFICATION SIGNALS TO IDENTIFY IN THE ASSESSMENT:\\n"
                for signal in self.selling_product.qualification_signals:
                    if signal.is_confirmed:
                        signals_section += f"- {signal.name}: {signal.description} (Importance: {signal.importance}/5)\\n"
            
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
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
                extracted_json = json_match.group(1) if json_match else content
                
                # Parse the extracted JSON
                fit_data = repair_loads(extracted_json)
                
                # Parse fit_score, ensuring it's a valid float
                try:
                    score_val = fit_data.get("fit_score")
                    if score_val is None:
                        # If no score was provided, derive from fit_level
                        level = fit_data.get("fit_level", "unknown").lower()
                        result.fit_score = FIT_LEVEL_SCORES.get(level, 0.5)
                        if self.verbose:
                            print(f"No score provided, derived {result.fit_score} from level: {level}")
                    else:
                        # Try to convert to float, with fallback
                        try:
                            result.fit_score = float(score_val)
                        except (ValueError, TypeError):
                            # If conversion fails, derive from fit_level
                            level = fit_data.get("fit_level", "unknown").lower()
                            result.fit_score = FIT_LEVEL_SCORES.get(level, 0.5)
                            if self.verbose:
                                print(f"Invalid score '{score_val}', using {result.fit_score} from level: {level}")
                except Exception as e:
                    # Default to moderate score if any errors
                    result.fit_score = 0.5
                    if self.verbose:
                        print(f"Error processing fit score: {e}, using default: 0.5")
                
                # Update the result with extracted data
                result.fit_level = FitLevel(fit_data.get("fit_level", "unknown").lower())
                result.fit_explanation = fit_data.get("fit_explanation", "")
                result.pain_points = fit_data.get("pain_points", [])
                result.value_propositions = fit_data.get("value_propositions", [])
                result.objection_handling = fit_data.get("objection_handling", [])
                result.key_decision_makers = fit_data.get("key_decision_makers", [])
                
                # Log the raw fit score for debugging
                if self.verbose:
                    print(f"Raw fit score from assessment: {result.fit_score:.2f}")
                
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
                
                # Adjust fit score based on matched signals if there are confirmed signals
                confirmed_signals = [s for s in self.selling_product.qualification_signals if s.is_confirmed]
                if confirmed_signals and result.matched_signals:
                    signal_score_adjustment = self._calculate_signal_score(result.matched_signals, confirmed_signals)
                    # Blend original fit score with signal score using configured weights
                    result.fit_score = (result.fit_score * BASE_SCORE_WEIGHT) + (signal_score_adjustment * SIGNAL_WEIGHT)
                    if self.verbose:
                        print(f"Signal score adjustment: {signal_score_adjustment:.2f}, Final adjusted score: {result.fit_score:.2f}")
                        print(f"Matched {len(result.matched_signals)} of {len(confirmed_signals)} qualification signals")
                else:
                    # If no signal matching, use the raw LLM score but make sure it's not 0
                    if result.fit_score == 0.0:
                        # Map fit level to default scores if the score is 0
                        level = result.fit_level.value if isinstance(result.fit_level, Enum) else str(result.fit_level).lower()
                        result.fit_score = FIT_LEVEL_SCORES.get(level, 0.5)
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
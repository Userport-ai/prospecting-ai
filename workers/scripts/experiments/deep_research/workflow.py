"""Enhanced workflow for streamlined screening and detailed qualification signal matching."""

import asyncio
import json
import os
import time
from typing import List, Optional
from datetime import datetime

import re
from .config import TIMEOUTS, MAX_QUALIFICATION_SIGNALS, FIT_LEVEL_SCORES
from .data_models import (
    ProspectingTarget, SellingProduct, ProspectingResult, ResearchStep, 
    ResearchStepResult, ResearchStatus, FitLevel, QualificationSignal,
    MatchedSignal, ConfidenceLevel
)
from .research_engine import ProspectingResearchEngine
from json_repair import loads as repair_loads

class ProspectingWorkflow:
    """Streamlined workflow focused on screening with enhanced qualification signals."""
    
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
        
        # Initialize with streamlined research steps
        self.research_steps = []
        self._setup_streamlined_steps()
    
    async def identify_qualification_signals(self, product: SellingProduct, research: str, interactive: bool = False) -> List[QualificationSignal]:
        """
        Identify qualification signals from selling product research.
        Enhanced to create more specific, measurable signals with clear detection criteria.
        """
        print("\n=== Identifying Qualification Signals ===\n")
        
        try:
            # Prompt to identify qualification signals with enhanced specificity
            signals_prompt = f"""
            Based on the research about {product.name}, identify the top {MAX_QUALIFICATION_SIGNALS * 2} qualification signals 
            that would indicate a prospective customer is an ideal fit for this product. 
            
            IMPORTANT: These signals should be extremely specific, measurable, and easily verifiable through research.
            Examples of good signals:
            - "Has 500+ employees in IT department"
            - "Uses AWS for cloud infrastructure"
            - "Recent funding round of $10M+"
            - "Currently using competitor X"
            - "Operates in regulated industry (healthcare/finance)"
            
            PRODUCT RESEARCH:
            {research}
            
            For each signal:
            1. Name: Extremely specific and measurable (e.g., "Uses Salesforce CRM", not just "Has CRM")
            2. Description: Detailed explanation of why this exact signal matters for our product
            3. Importance: 1-5 scale where:
               - 5: Must-have signal - disqualify if absent
               - 4: Strong indicator - significantly increases fit
               - 3: Good indicator - moderately increases fit
               - 2: Nice-to-have - slight positive signal
               - 1: Minor indicator - marginal impact
            4. Detection Instructions: Step-by-step process to verify this signal, including:
               - Specific keywords to search for
               - Where to look (website sections, news, tech stack tools)
               - What evidence confirms or denies this signal
            
            Return your response as a JSON array with this structure:
            [
              {{
                "name": "Specific measurable signal",
                "description": "Detailed explanation of relevance",
                "importance": 5,
                "detection_instructions": "1. Check X using tool Y\\n2. Look for keywords Z\\n3. Verify by..."
              }},
              ...
            ]
            
            Focus on signals that are:
            - Easily verifiable through web research or tools
            - Binary (yes/no) or quantifiable (number, percentage)
            - Directly related to product fit
            - Based on actual company characteristics, not assumptions
            """
            
            # Get signals from LLM
            response = await self.engine.pro_llm.ainvoke(signals_prompt)
            signals_text = response.content
            
            # Extract the JSON
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', signals_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = signals_text
            
            # Parse and create signal objects
            try:
                signals_data = repair_loads(json_str)
                if not isinstance(signals_data, list):
                    raise ValueError("Expected a list of signals")
                
                signals = []
                for signal_data in signals_data[:MAX_QUALIFICATION_SIGNALS * 2]:  # Get more initially
                    signals.append(QualificationSignal(
                        name=signal_data.get("name", ""),
                        description=signal_data.get("description", ""),
                        importance=signal_data.get("importance", 3),
                        detection_instructions=signal_data.get("detection_instructions", ""),
                        is_confirmed=not interactive  # Auto-confirm in non-interactive mode
                    ))
                
                # Sort by importance and take top signals
                signals.sort(key=lambda x: x.importance, reverse=True)
                signals = signals[:MAX_QUALIFICATION_SIGNALS]
                
                # Print signals
                print(f"Identified {len(signals)} qualification signals:")
                for i, signal in enumerate(signals, 1):
                    print(f"\n{i}. {signal.name}")
                    print(f"   Importance: {signal.importance}/5")
                    print(f"   Description: {signal.description}")
                    print(f"   Detection: {signal.detection_instructions[:100]}...")
                
                # In interactive mode, allow confirmation/editing
                if interactive:
                    signals = await self.confirm_edit_signals(signals)
                
                # Update the product with signals
                product.qualification_signals = signals
                
                # Final summary
                print(f"\n=== Final {len(signals)} Qualification Signals ===")
                for i, signal in enumerate(signals, 1):
                    print(f"{i}. {signal.name} (Importance: {signal.importance}/5)")
                
                return signals
                
            except Exception as e:
                print(f"Error parsing signals JSON: {str(e)}")
                raise
                
        except Exception as e:
            print(f"Error identifying qualification signals: {str(e)}")
            # Return minimal fallback signals
            fallback_signals = [
                QualificationSignal(
                    name="Enterprise Scale (500+ employees)",
                    description="Larger companies have budget and need for our solution",
                    importance=4,
                    detection_instructions="Check company size on website, LinkedIn, or company directories",
                    is_confirmed=True
                ),
                QualificationSignal(
                    name="Technology Adoption Indicator",
                    description="Companies using modern tech are more likely to adopt new solutions",
                    importance=3,
                    detection_instructions="Check tech stack using BuiltWith or by analyzing their careers page",
                    is_confirmed=True
                )
            ]
            product.qualification_signals = fallback_signals
            return fallback_signals
    
    async def confirm_edit_signals(self, signals: List[QualificationSignal]) -> List[QualificationSignal]:
        """
        Interactive confirmation and editing of qualification signals.
        Can be called separately after signal identification or as part of the workflow.
        """
        confirmed_signals = []
        print("\n=== Confirm Qualification Signals ===")
        
        for signal in signals:
            print(f"\nSignal: {signal.name}")
            print(f"Description: {signal.description}")
            print(f"Importance: {signal.importance}/5")
            print(f"Detection: {signal.detection_instructions}")
            
            response = input("\nInclude this signal? (y/n/e for edit): ").lower()
            
            if response == 'y':
                signal.is_confirmed = True
                confirmed_signals.append(signal)
                print("Signal confirmed.")
            elif response == 'e':
                # Allow editing
                new_name = input(f"Name [{signal.name}]: ").strip() or signal.name
                new_desc = input(f"Description [{signal.description[:50]}...]: ").strip() or signal.description
                new_imp = input(f"Importance [{signal.importance}]: ").strip() or str(signal.importance)
                new_inst = input(f"Detection [{signal.detection_instructions[:50]}...]: ").strip() or signal.detection_instructions
                
                signal.name = new_name
                signal.description = new_desc
                signal.importance = int(new_imp) if new_imp.isdigit() else signal.importance
                signal.detection_instructions = new_inst
                signal.is_confirmed = True
                confirmed_signals.append(signal)
                print("Signal edited and confirmed.")
            else:
                print("Signal skipped.")
        
        # Option to add custom signals
        while True:
            add_custom = input("\nAdd a custom qualification signal? (y/n): ").lower()
            if add_custom != 'y':
                break
                
            name = input("Signal name: ")
            desc = input("Description: ")
            imp = input("Importance (1-5): ")
            inst = input("Detection instructions: ")
            
            importance = 3
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
        
        # Final summary
        print(f"\n=== Final {len(confirmed_signals)} Qualification Signals ===")
        for i, signal in enumerate(confirmed_signals, 1):
            print(f"{i}. {signal.name} (Importance: {signal.importance}/5)")
        
        return confirmed_signals[:MAX_QUALIFICATION_SIGNALS]
    
    def _setup_streamlined_steps(self):
        """Set up streamlined research steps focused on screening efficiency."""
        base_steps = [
            # Step 1: Quick Company Overview (enriched with Apollo)
            ResearchStep(
                step_id="company_essentials",
                question="What are the essential facts about this company?",
                prompt_template="""
                Provide essential company information for quick screening:
                
                REQUIRED INFORMATION:
                1. Company basics: name, website, industry, founded year
                2. Size: employee count, revenue (if available)
                3. Business model: B2B/B2C, primary offerings
                4. Market focus: target customers, key verticals
                5. Headquarters and major locations
                6. Recent funding (if any)
                7. Key leadership (CEO, CTO if relevant)
                
                Use Apollo.io data for enriched company profile including LinkedIn URL,
                funding details, and accurate employee count.
                
                Keep responses factual and concise - aim for rapid screening efficiency.
                """,
                use_apollo=True
            ),
            
            # Step 2: Technology & Operations Scan
            ResearchStep(
                step_id="tech_operations",
                question="What technology does this company use and how do they operate?",
                prompt_template="""
                Research the company's technology and operations:
                
                1. TECHNOLOGY STACK:
                   - Use BuiltWith data to identify their tech stack
                   - Core business systems (CRM, ERP, etc.)
                   - Development technologies and platforms
                   - Cloud infrastructure and tools
                   
                2. OPERATIONAL INDICATORS:
                   - Digital maturity level
                   - Innovation indicators (R&D, patents, tech initiatives)
                   - Automation level
                   - Security/compliance focus
                
                3. BUSINESS PRIORITIES:
                   - Recent technology investments
                   - Digital transformation initiatives
                   - Hiring focus areas (from job postings)
                
                Focus on factual findings that indicate readiness for new solutions.
                BuiltWith data will be automatically included for tech stack analysis.
                """,
                depends_on=["company_essentials"],
                use_builtwith=True
            ),
            
            # Step 3: Recent Developments & Signals
            ResearchStep(
                step_id="market_signals",
                question="What recent developments and market signals indicate company direction?",
                prompt_template="""
                Identify recent developments and market signals (last 12 months):
                
                1. GROWTH INDICATORS:
                   - Funding rounds or acquisitions
                   - New product launches
                   - Market expansion
                   - Partnership announcements
                   
                2. ORGANIZATIONAL CHANGES:
                   - Leadership changes
                   - Restructuring
                   - Strategic pivots
                   - Hiring patterns
                
                3. CHALLENGES & OPPORTUNITIES:
                   - Mentioned pain points in press/interviews
                   - Competitive pressures
                   - Regulatory changes affecting them
                   - Market opportunities they're pursuing
                
                4. BUYING SIGNALS:
                   - Technology modernization initiatives
                   - Process improvement focus
                   - Budget allocations
                   - Vendor evaluation activities
                
                Include specific dates and sources for key findings.
                Focus on signals that indicate readiness for new solutions.
                """,
                depends_on=["company_essentials", "tech_operations"]
            )
        ]
        
        self.research_steps = base_steps
    
    def _create_qualification_steps(self, signals: List[QualificationSignal]) -> List[ResearchStep]:
        """Dynamically create one step per qualification signal."""
        if not signals:
            return []
        
        qualification_steps = []
        
        # Sort signals by importance (highest first)
        sorted_signals = sorted(signals, key=lambda s: s.importance, reverse=True)
        
        # Create one step per signal
        for i, signal in enumerate(sorted_signals, 1):
            # Create step-specific prompt
            signal_prompt = f"""
            Research and verify this specific qualification signal for {{company_name}}:
            
            SIGNAL: {signal.name} (Importance: {signal.importance}/5)
            
            WHAT TO VERIFY:
            {signal.description}
            
            HOW TO DETECT:
            {signal.detection_instructions}
            
            RESEARCH REQUIREMENTS:
            1. Search for specific evidence using all available tools
            2. Provide clear verdict: MATCH (yes), NO MATCH, or PARTIAL MATCH
            3. Include specific proof or evidence found
            4. Rate confidence in your finding: HIGH, MEDIUM, or LOW
            5. If no evidence found, explain what you searched and why it's absent
            
            FOCUS LEVEL:
            """
            
            # Add importance-specific instructions
            if signal.importance >= 4:
                signal_prompt += """
            This is a CRITICAL signal - be thorough and comprehensive in verification.
            Spend adequate time to ensure accuracy. A false negative could disqualify a good prospect.
            """
            elif signal.importance == 3:
                signal_prompt += """
            This is an IMPORTANT signal - balance thoroughness with efficiency.
            Verify carefully. Focus on clear evidence.
            """
            else:
                signal_prompt += """
            This is a SUPPLEMENTARY signal - verify quickly and efficiently.
            Don't spend excessive time. Report if easily found, otherwise move on.
            """
            
            signal_prompt += """
            
            RESPONSE FORMAT:
            - Verdict: [MATCH/NO MATCH/PARTIAL MATCH]
            - Evidence: [Specific findings supporting your verdict]
            - Confidence: [HIGH/MEDIUM/LOW]
            - Search Summary: [What sources you checked]
            """
            
            # Create unique step ID for each signal
            step_id = f"signal_{i}_{signal.name.lower().replace(' ', '_')[:20]}"
            
            # Dependencies - depends on base research steps and any previous signal steps
            depends_on = ["company_essentials", "tech_operations", "market_signals"]
            
            # Add dependencies on previous signal steps for sequential execution
            for j in range(1, i):
                prev_signal = sorted_signals[j-1]
                prev_step_id = f"signal_{j}_{prev_signal.name.lower().replace(' ', '_')[:20]}"
                depends_on.append(prev_step_id)
            
            qualification_steps.append(ResearchStep(
                step_id=step_id,
                question=f"Do they match signal: {signal.name}?",
                prompt_template=signal_prompt,
                depends_on=depends_on
            ))
        
        return qualification_steps
    
    @staticmethod
    def _create_final_assessment_step(signals: List[QualificationSignal]) -> ResearchStep:
        """Create the final fit assessment step that synthesizes all findings."""
        assessment_prompt = f"""
        Provide a comprehensive fit assessment for {{company_name}} based on all research.
        
        OUR SOLUTION:
        {{selling_product_info}}
        
        QUALIFICATION SIGNALS TO CONSIDER:
        """
        
        # Sort signals by importance for the assessment
        sorted_signals = sorted(signals, key=lambda s: s.importance, reverse=True)
        
        for signal in sorted_signals:
            assessment_prompt += f"""
        - {signal.name} (Importance: {signal.importance}/5): {signal.description}
        """
        
        assessment_prompt += """
        
        FINAL ASSESSMENT STRUCTURE:
        
        1. OVERALL FIT LEVEL:
           - Rate as: EXCELLENT, GOOD, MODERATE, POOR, or UNSUITABLE
           - Provide 0.0-1.0 numerical score
           - Explain the rating with specific evidence
        
        2. SIGNAL MATCHES SUMMARY:
           Review each signal verification step and summarize:
           - Match status (YES/NO/PARTIAL)
           - Supporting evidence
           - Impact on overall fit
           - Weight the importance of each signal in your assessment
        
        3. VALUE PROPOSITION:
           - Primary value our solution provides this company
           - Specific use cases for their context
           - Expected ROI or impact
        
        4. PAIN POINT ALIGNMENT:
           - Their key challenges we solve
           - How our solution addresses each
           - Priority/urgency indicators
        
        5. CONCERNS & OBSTACLES:
           - Potential objections
           - Implementation challenges
           - Competitive considerations
        
        6. NEXT STEPS:
           - Recommended approach strategy
           - Key stakeholders to target
           - Optimal timing considerations
        
        7. CONFIDENCE ASSESSMENT:
           - Overall confidence in this assessment (HIGH/MEDIUM/LOW)
           - Data quality notes
           - Information gaps
        
        Provide a clear GO/NO-GO recommendation with supporting rationale.
        Focus on actionable insights for the sales team.
        """
        
        depends_on = ["company_essentials", "tech_operations", "market_signals"]
        
        # Add dependencies on all signal steps
        for i, signal in enumerate(sorted_signals, 1):
            step_id = f"signal_{i}_{signal.name.lower().replace(' ', '_')[:20]}"
            depends_on.append(step_id)
        
        return ResearchStep(
            step_id="final_assessment",
            question="What is our final fit assessment and recommendation?",
            prompt_template=assessment_prompt,
            depends_on=depends_on
        )
    
    async def research_target(self, target: ProspectingTarget) -> ProspectingResult:
        """Execute the streamlined research workflow with dynamic signal verification."""
        start_time = time.time()
        
        if self.verbose:
            print(f"\n=== Starting research for {target.company_name} at {datetime.now().strftime('%H:%M:%S')} ===\n")
        
        # Create dynamic research steps based on qualification signals
        all_steps = self.research_steps.copy()
        
        # Add signal verification steps
        if self.selling_product.qualification_signals:
            signal_steps = self._create_qualification_steps(self.selling_product.qualification_signals)
            all_steps.extend(signal_steps)
        
        # Add final assessment step
        final_step = self._create_final_assessment_step(self.selling_product.qualification_signals)
        all_steps.append(final_step)
        
        # Update research steps
        self.research_steps = all_steps
        
        # Initialize result
        result = ProspectingResult(
            target=target,
            selling_product=self.selling_product
        )
        
        # Execute steps with timeout
        try:
            async with asyncio.timeout(TIMEOUTS["account_research"]):
                for step in self._get_steps_in_execution_order():
                    step_start = time.time()
                    
                    step_result = await self.engine.research_step(
                        target=target,
                        step=step,
                        previous_results={k: v for k, v in result.steps.items()}
                    )
                    
                    step_duration = time.time() - step_start
                    if self.verbose:
                        print(f"Step {step.step_id} completed in {step_duration:.1f} seconds")
                    
                    result.steps[step.step_id] = step_result
                    
                    if step_result.status in [ResearchStatus.FAILED, ResearchStatus.TIMEOUT]:
                        print(f"Step {step.step_id} {step_result.status}: {step_result.error}")
                
                # Process final assessment
                await self._process_fit_assessment(result)
                
                # Calculate research quality
                self._calculate_research_quality(result)
        
        except asyncio.TimeoutError:
            print(f"Research for {target.company_name} timed out after {TIMEOUTS['account_research']} seconds")
            result.overall_status = ResearchStatus.TIMEOUT
        
        # Complete research
        end_time = time.time()
        total_duration = end_time - start_time
        result.mark_completed(start_time)
        result.total_time_seconds = total_duration
        
        if self.verbose:
            print(f"\n=== Completed research for {target.company_name} in {total_duration:.1f} seconds ===\n")
        
        return result
    
    async def _process_fit_assessment(self, result: ProspectingResult):
        """Extract key data from the final assessment with focus on qualification signals."""
        final_assessment = result.steps.get("final_assessment")
        
        if not final_assessment or final_assessment.status != ResearchStatus.COMPLETED:
            return
        
        try:
            # Process signal matches from individual signal verification steps
            all_signal_matches = []
            
            # Get sorted signals to iterate through steps in the same order
            sorted_signals = sorted(self.selling_product.qualification_signals, key=lambda s: s.importance, reverse=True)
            
            for i, signal in enumerate(sorted_signals, 1):
                step_id = f"signal_{i}_{signal.name.lower().replace(' ', '_')[:20]}"
                
                if step_id in result.steps and result.steps[step_id].status == ResearchStatus.COMPLETED:
                    signal_text = result.steps[step_id].answer
                    
                    # Enhanced signal extraction prompt
                    signal_prompt = f"""
                    Extract the signal match result from this research output:
                    
                    {signal_text}
                    
                    The signal being verified was: "{signal.name}"
                    
                    Extract:
                    - matched: "yes" (for MATCH), "no" (for NO MATCH), "partial" (for PARTIAL MATCH)
                    - evidence: The specific evidence found
                    - confidence: HIGH/MEDIUM/LOW
                    
                    Return as JSON object.
                    """
                    
                    response = await self.engine.llm.ainvoke(signal_prompt)
                    try:
                        import re
                        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response.content)
                        extracted = json_match.group(1) if json_match else response.content
                        signal_data = repair_loads(extracted)
                        
                        if isinstance(signal_data, dict):
                            signal_data['name'] = signal.name
                            signal_data['importance'] = signal.importance
                            all_signal_matches.append(signal_data)
                    except:
                        # Fallback: try to extract from text
                        if "MATCH" in signal_text.upper() and "NO MATCH" not in signal_text.upper():
                            match_status = "partial" if "PARTIAL" in signal_text.upper() else "yes"
                        else:
                            match_status = "no"
                        
                        all_signal_matches.append({
                            "name": signal.name,
                            "importance": signal.importance,
                            "matched": match_status,
                            "evidence": "Extracted from research step",
                            "confidence": "MEDIUM"
                        })
            
            # Process final assessment
            fit_prompt = f"""
            Extract the key information from this fit assessment into a structured format.
            
            ASSESSMENT: {final_assessment.answer}
            
            QUALIFICATION SIGNALS DATA: {json.dumps(all_signal_matches)}
            
            Extract the following in JSON format:
            - fit_level: The overall fit level (excellent, good, moderate, poor, unsuitable)
            - fit_score: A numerical score from 0.0 to 1.0
            - fit_explanation: A brief explanation of the fit assessment
            - pain_points: List of pain points our product addresses (max 5)
            - value_propositions: List of value props for this company (max 5)
            - objection_handling: List of potential objections and responses (max 3)
            - key_decision_makers: List of stakeholders to target
            - matched_signals: List of matched qualification signals with importance and evidence
            - recommendation: GO/NO-GO with brief rationale
            - confidence_level: HIGH/MEDIUM/LOW for overall assessment
            
            Return ONLY the JSON.
            """
            
            response = await self.engine.llm.ainvoke(fit_prompt)
            content = response.content
            
            # Extract JSON
            import re
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            extracted_json = json_match.group(1) if json_match else content
            
            # Parse fit data
            fit_data = repair_loads(extracted_json)
            
            # Update result with fit data
            result.fit_level = FitLevel(fit_data.get("fit_level", "unknown").lower())
            result.fit_score = float(fit_data.get("fit_score", 0.5))
            result.fit_explanation = fit_data.get("fit_explanation", "")
            result.pain_points = fit_data.get("pain_points", [])[:5]
            result.value_propositions = fit_data.get("value_propositions", [])[:5]
            result.objection_handling = fit_data.get("objection_handling", [])[:3]
            result.key_decision_makers = fit_data.get("key_decision_makers", [])
            
            # Process matched signals with importance from original signals
            matched_signals = []
            signal_matches = fit_data.get("matched_signals", [])
            
            for match in signal_matches:
                # Find original signal to get importance
                original_signal = None
                for sig in self.selling_product.qualification_signals:
                    if sig.name.lower() in match.get("name", "").lower() or match.get("name", "").lower() in sig.name.lower():
                        original_signal = sig
                        break
                
                matched_signal = MatchedSignal(
                    name=match.get("name", ""),
                    importance=original_signal.importance if original_signal else match.get("importance", 3),
                    evidence=match.get("evidence", ""),
                    description=original_signal.description if original_signal else ""
                )
                matched_signals.append(matched_signal)
            
            result.matched_signals = matched_signals
            
            # Set confidence
            confidence_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
            confidence_level = fit_data.get("confidence_level", "medium").lower()
            result.fit_confidence = confidence_map.get(confidence_level, 0.7)
            
        except Exception as e:
            print(f"Error processing fit assessment: {str(e)}")
            result.fit_level = FitLevel.UNKNOWN
            result.fit_score = 0.5
            result.fit_confidence = 0.0
    
    def _calculate_research_quality(self, result: ProspectingResult):
        """Calculate overall research quality based on step completions and signal matches."""
        completed_steps = sum(1 for step in result.steps.values() 
                            if step.status == ResearchStatus.COMPLETED)
        total_steps = len(result.steps)
        
        # Base quality on completion rate
        completion_score = completed_steps / total_steps if total_steps > 0 else 0
        
        # Factor in signal match quality
        if self.selling_product.qualification_signals:
            total_signals = len(self.selling_product.qualification_signals)
            matched_signals = len(result.matched_signals)
            signal_score = matched_signals / total_signals if total_signals > 0 else 0.5
            
            # Weight by importance of matched signals
            importance_weight = sum(s.importance for s in result.matched_signals)
            total_importance = sum(s.importance for s in self.selling_product.qualification_signals)
            importance_score = importance_weight / total_importance if total_importance > 0 else 0
            
            # Combine scores
            quality_score = (completion_score * 0.4) + (signal_score * 0.3) + (importance_score * 0.3)
        else:
            quality_score = completion_score
        
        result.research_quality_score = quality_score
        result.fit_confidence = min(result.fit_confidence * quality_score, 1.0)
        
        # Set validation summary
        if quality_score >= 0.8:
            result.validation_summary = f"High-quality research: {quality_score:.0%} complete with {len(result.matched_signals)} signals matched"
        elif quality_score >= 0.6:
            result.validation_summary = f"Moderate research quality: {quality_score:.0%} complete"
        else:
            result.validation_summary = f"Limited research: {quality_score:.0%} complete"
    
    def _get_steps_in_execution_order(self) -> List[ResearchStep]:
        """Get research steps in proper execution order based on dependencies."""
        # Simple topological sort
        ordered = []
        remaining = self.research_steps.copy()
        
        while remaining:
            # Find steps with no unresolved dependencies
            ready = []
            for step in remaining:
                if not step.depends_on:
                    ready.append(step)
                else:
                    # Check if all dependencies are already in ordered list
                    deps_met = all(dep in [s.step_id for s in ordered] 
                                 for dep in step.depends_on)
                    if deps_met:
                        ready.append(step)
            
            if not ready:
                # Circular dependency or missing dependency
                print("Warning: Could not resolve all dependencies")
                ordered.extend(remaining)
                break
            
            # Add ready steps to ordered list
            for step in ready:
                ordered.append(step)
                remaining.remove(step)
        
        return ordered
    
    def save_results(self, result: ProspectingResult, path: str = None, db_manager=None):
        """Save research results to file."""
        if path is None:
            base_filename = f"prospect_{result.target.company_name.replace(' ', '_').lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            path = f"{base_filename}.json"
        else:
            # Extract base filename without extension
            base_filename = path.rsplit('.', 1)[0] if '.' in path else path
        
        # Save the JSON result
        with open(path, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        # Generate and save markdown report to file
        try:
            # Generate markdown (either from database manager or directly)
            if db_manager:
                markdown_content = db_manager._generate_markdown_from_result(result)
            else:
                # Simplified markdown generation if no database manager
                markdown_content = self._generate_simple_markdown(result)
            
            # Save to file
            markdown_path = f"{base_filename}.md"
            with open(markdown_path, 'w') as f:
                f.write(markdown_content)
            
            if self.verbose:
                print(f"Saved markdown report to {markdown_path}")
        except Exception as e:
            print(f"Error saving markdown report: {e}")
        
        if self.verbose:
            print(f"Results saved to {path}")
            
    def _generate_simple_markdown(self, result: ProspectingResult) -> str:
        """Generate a simple markdown report when db_manager is not available."""
        try:
            markdown = f"# Research Report: {result.target.company_name}\n\n"
            markdown += f"- Website: [{result.target.website}]({result.target.website})\n"
            markdown += f"- Industry: {result.target.industry or 'Unknown'}\n"
            
            # Use safer attribute access for enum values
            fit_level = result.fit_level
            if hasattr(result.fit_level, 'value'):
                fit_level = result.fit_level.value
                
            markdown += f"- Fit Level: {fit_level}\n"
            markdown += f"- Fit Score: {result.fit_score:.2f}/1.0\n"
            markdown += f"- Research Completed: {result.completed_at}\n\n"
            
            # Write each research step's raw output
            markdown += "## Research Steps\n\n"
            for step_id, step in result.steps.items():
                # Safely check completion status
                status = step.status
                if hasattr(step.status, "value"):
                    status = step.status.value
                    
                if status == "completed":
                    markdown += f"### {step_id.replace('_', ' ').title()}\n\n"
                    markdown += f"**Question**: {step.question}\n\n"
                    markdown += f"{step.answer}\n\n"
                    if hasattr(step, 'sources') and step.sources:
                        markdown += "**Sources**:\n"
                        for source in step.sources:
                            markdown += f"- {source}\n"
                        markdown += "\n"
                    markdown += "---\n\n"
            
            # Add matched signals section
            if result.matched_signals:
                markdown += "## Matched Qualification Signals\n\n"
                for signal in sorted(result.matched_signals, key=lambda x: x.importance, reverse=True):
                    markdown += f"- **{signal.name}** (Importance: {signal.importance}/5)\n"
                    if hasattr(signal, "evidence") and signal.evidence:
                        markdown += f"  Evidence: {signal.evidence}\n"
            
            return markdown
            
        except Exception as e:
            print(f"Error generating simple markdown: {e}")
            # Return a basic markdown if we encounter an error
            return f"# Research Report: {result.target.company_name}\n\nResearch completed on {result.completed_at}"
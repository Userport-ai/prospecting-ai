"""Main entry point and high-level functions for the deep research prospecting tool."""

import argparse
import asyncio
import json
import os
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from .apollo_source import ApolloCompanySource
from .config import APOLLO_API_CONFIG, COMMON_FILTER_TEMPLATES
from .data_models import (
    ProspectingTarget, SellingProduct, ProspectingResult
)
from .database import DatabaseManager
from .utils import load_targets_from_csv, format_time
from .workflow_enhanced import ProspectingWorkflow


async def research_selling_product(product: SellingProduct, engine) -> str:
    print(f"\n=== Researching Selling Product: {product.name} ===\n")
    
    try:
        from .data_models import ResearchStep, ResearchStatus, ProspectingTarget
        
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
        
        # Create a temporary workflow object to use its identify_qualification_signals method
        temp_workflow = ProspectingWorkflow(
            selling_product=product, 
            selling_product_research="",
            model_name=engine.model_name,  # Use the same model name
            verbose=engine.verbose  # Use the same verbosity setting
        )
        
        # Generate qualification signals from the research using the engine's LLM
        await temp_workflow.identify_qualification_signals(product, step_result.answer, interactive=False)
        
        # Store the research in the engine for use in formatting prompts
        engine.selling_product_research = step_result.answer
        
        return step_result.answer
    
    except Exception as e:
        print(f"Error researching selling product: {str(e)}")
        return f"Error researching product: {str(e)}"


async def research_single_target(target: ProspectingTarget, product: SellingProduct, output_dir: str, 
                                db_manager: Optional[DatabaseManager] = None) -> ProspectingResult:
    """Research a single target company."""
    start_time = time.time()
    
    from .research_engine import ProspectingResearchEngine
    engine = ProspectingResearchEngine(selling_product=product, verbose=True, selling_product_research="")
    
    # Research the selling product once
    selling_product_research = await research_selling_product(product, engine)
    
    # Create workflow with researched selling product
    workflow = ProspectingWorkflow(
        selling_product=product,
        selling_product_research=selling_product_research,
        verbose=True
    )
    
    result = await workflow.research_target(target)
    
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
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Print summary
    print("\nRESEARCH SUMMARY:")
    print(f"Target: {result.target.company_name}")
    print(f"Website: {result.target.website}")
    print(f"Fit Level: {result.fit_level}")
    print(f"Fit Score: {result.fit_score:.2f}")
    print(f"Total Time: {format_time(total_duration)}")
    
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


async def generate_targets_from_apollo(
    product: SellingProduct, 
    model,
    max_companies: int = None, 
    manual_filters: Optional[Dict[str, Any]] = None,
    filter_template: Optional[str] = None,
    use_ai_filters: bool = True,
    interactive: bool = False,
    include_filter_explanation: bool = False
) -> List[ProspectingTarget]:
    """
    Generate target companies from Apollo API based on product information.
    
    Args:
        product: The selling product
        model: LLM model for AI-derived filters
        max_companies: Maximum number of companies to return
        manual_filters: Dictionary of Apollo API filter parameters
        filter_template: Name of a predefined filter template from config
        use_ai_filters: Whether to use AI to derive filters
        interactive: Whether to allow interactive confirmation/editing of filters
        include_filter_explanation: Whether to return filter explanation
        
    Returns:
        List of ProspectingTarget objects
    """
    # Use default max companies from config if not specified
    if max_companies is None:
        max_companies = APOLLO_API_CONFIG.get("default_max_companies", 10)
    
    # Initialize Apollo API client with config from settings
    apollo_client = ApolloCompanySource(
        concurrency_limit=APOLLO_API_CONFIG.get("concurrency_limit", 3),
        rate_limit_delay=APOLLO_API_CONFIG.get("rate_limit_delay", 1.0),
        cache_results=APOLLO_API_CONFIG.get("cache_results", True),
        cache_ttl=APOLLO_API_CONFIG.get("cache_ttl", 3600)
    )
    
    try:
        # Determine filters to use
        search_filters = {}
        
        # 1. If manual filters provided, use those
        if manual_filters:
            search_filters = manual_filters
            print(f"Using provided manual filters")
            
        # 2. If template specified, use that template
        elif filter_template and filter_template in COMMON_FILTER_TEMPLATES:
            search_filters = COMMON_FILTER_TEMPLATES[filter_template]
            print(f"Using filter template: {filter_template}")
            
        # 3. Use AI to derive filters if enabled, but not passing to client yet
        # (client will derive filters itself with interactive mode if needed)
        elif use_ai_filters and not interactive:
            # Get product description for filter derivation
            product_desc = product.description
            if not product_desc and hasattr(product, 'value_proposition') and product.value_proposition:
                product_desc = product.value_proposition
                
            # If still no description, create a minimal one from other fields
            if not product_desc:
                features = ", ".join(product.key_features[:3]) if product.key_features else "no features specified"
                industries = ", ".join(product.target_industries[:3]) if product.target_industries else "unspecified industries"
                product_desc = f"A product targeting {industries} with key features: {features}."
            
            print("Deriving filters from product information using AI...")
            search_filters, explanation = await apollo_client.derive_initial_filters(
                product.name,
                product_desc,
                model,
                also_explain=True
            )
            
            # Print the customer profile analysis
            print("\n=== IDEAL CUSTOMER PROFILE ANALYSIS ===\n")
            print(explanation)
            
        # 4. For interactive mode or when not using AI filters, we'll let the client handle it
        elif not use_ai_filters:
            search_filters = APOLLO_API_CONFIG.get("default_filters", {})
            print("Using default filters")
        else:
            # When interactive mode is enabled but use_ai_filters is disabled,
            # we still want the client to show default filters
            search_filters = {}
            
        # Log the filters being used (if not interactive mode)
        if not interactive and search_filters:
            print("\nApollo API Search Filters:")
            for k, v in search_filters.items():
                print(f"  {k}: {v}")
        
        # Get product description for Apollo API
        product_desc = product.description
        if not product_desc and hasattr(product, 'value_proposition') and product.value_proposition:
            product_desc = product.value_proposition
        
        # Get companies from Apollo API
        print(f"\nSearching for up to {max_companies} companies matching filters...")
        
        # Handle different return types based on whether we want the filter explanation
        if include_filter_explanation:
            try:
                result = await apollo_client.get_companies_for_product(
                    product.name,
                    product_desc or "",
                    model,
                    max_companies=max_companies,
                    use_ai_filters=use_ai_filters and not search_filters,  # Only derive if we haven't already
                    manual_filters=search_filters if search_filters else None,
                    interactive=interactive,
                    include_filter_explanation=True
                )
                
                # Unpack the result (targets, filters, explanation)
                if isinstance(result, tuple) and len(result) == 3:
                    targets, actual_filters, explanation = result
                    
                    # If we had no filters originally but got filters from interactive mode,
                    # display them for the user
                    if not search_filters and actual_filters and not interactive:
                        print("\nApollo API Search Filters Used:")
                        for k, v in actual_filters.items():
                            print(f"  {k}: {v}")
                elif isinstance(result, list):
                    # Handle case where we got a list of targets directly
                    targets = result
                else:
                    # This shouldn't happen, but just in case
                    print("Warning: Unexpected result type from Apollo API")
                    targets = []
            except Exception as e:
                print(f"Error processing Apollo API results: {str(e)}")
                print("This appears to be a string formatting issue. Trying alternative approach...")
                
                # Try with simpler parameters
                try:
                    targets = await apollo_client.get_companies_for_product(
                        product.name,
                        product_desc or "",
                        model,
                        max_companies=max_companies,
                        use_ai_filters=use_ai_filters and not search_filters,
                        manual_filters=search_filters if search_filters else None,
                        interactive=interactive,
                        include_filter_explanation=False  # No explanation to avoid formatting issues
                    )
                except Exception as nested_e:
                    print(f"Still encountering issues: {str(nested_e)}")
                    targets = []
                
        else:
            # Simpler call when we don't need the explanation
            targets = await apollo_client.get_companies_for_product(
                product.name,
                product_desc or "",
                model,
                max_companies=max_companies,
                use_ai_filters=use_ai_filters and not search_filters,
                manual_filters=search_filters if search_filters else None,
                interactive=interactive,
                include_filter_explanation=False
            )
        
        # Clean up
        await apollo_client.close()
        
        if targets:
            print(f"Found {len(targets)} matching companies")
            # Display sample of companies found
            for i, target in enumerate(targets[:5], 1):
                print(f"  {i}. {target.company_name} - {target.website}")
            if len(targets) > 5:
                print(f"  ... and {len(targets) - 5} more")
        else:
            print("No matching companies found. Try adjusting filters.")
        
        return targets
        
    except Exception as e:
        print(f"Error generating targets from Apollo: {str(e)}")
        await apollo_client.close()
        return []


async def batch_research_targets(targets: List[ProspectingTarget], product: SellingProduct, 
                                output_dir: str, limit: int = 0, db_manager: Optional[DatabaseManager] = None):
    """Research multiple target companies."""
    global_start_time = time.time()
    
    if limit > 0 and limit < len(targets):
        targets = targets[:limit]
        print(f"Limited to {limit} targets")
    
    print(f"Starting research for {len(targets)} targets")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create research engine for selling product research
    from .research_engine import ProspectingResearchEngine
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
    successful_results = 0
    failed_results = 0
    
    for i, target in enumerate(targets, 1):
        target_start_time = time.time()
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
            successful_results += 1
            
            # Print target summary
            target_duration = time.time() - target_start_time
            print(f"Completed in {format_time(target_duration)}")
            print(f"Fit Level: {result.fit_level} ({result.fit_score:.2f})")
            if result.matched_signals:
                print(f"Matched Signals: {len(result.matched_signals)}")
            
        except Exception as e:
            print(f"Error researching target {target.company_name}: {str(e)}")
            failed_results += 1
    
    # Generate summary report
    global_duration = time.time() - global_start_time
    generate_summary_report(results, product, os.path.join(output_dir, "summary_report.json"), global_duration)
    
    # If database manager, generate signal analysis from DB
    if db_manager and selling_product_id:
        signals_summary = db_manager.get_signals_summary(selling_product_id)
        performance_summary = db_manager.get_performance_summary(selling_product_id)
        
        print("\nSignal Analysis from Database:")
        for signal_name, stats in signals_summary.items():
            print(f"  {signal_name}: {stats['match_count']} matches (Avg. Importance: {stats['avg_importance']:.1f}/5)")
        
        print("\nPerformance Summary:")
        print(f"  Total processed: {performance_summary['total_results']} targets")
        print(f"  Average time: {format_time(performance_summary['avg_time_seconds'])}")
        print(f"  Min time: {format_time(performance_summary['min_time_seconds'])}")
        print(f"  Max time: {format_time(performance_summary['max_time_seconds'])}")
        print(f"  Total time: {format_time(performance_summary['total_time_seconds'])}")
    
    # Print overall summary
    print("\nBATCH PROCESSING COMPLETE")
    print(f"Total time: {format_time(global_duration)}")
    print(f"Successfully processed: {successful_results}/{len(targets)}")
    if failed_results > 0:
        print(f"Failed: {failed_results}")
    
    return results


def generate_summary_report(results: List[ProspectingResult], product: SellingProduct, 
                           output_path: str, total_duration: float = 0.0):
    """Generate a summary report of all research results."""
    if not results:
        print("No results to generate summary report")
        return
    
    from enum import Enum
    
    summary = {
        "product": product.name,
        "total_targets": len(results),
        "timestamp": datetime.now().isoformat(),
        "total_duration_seconds": total_duration,
        "avg_time_per_target_seconds": total_duration / len(results) if results else 0,
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
    
    # Calculate timing statistics
    times = [result.total_time_seconds for result in results if result.total_time_seconds > 0]
    if times:
        summary["min_time_seconds"] = min(times) 
        summary["max_time_seconds"] = max(times)
        summary["avg_time_seconds"] = sum(times) / len(times)
    
    # Process each result
    for result in results:
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
            "time_seconds": result.total_time_seconds,
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
    print(f"Total Research Time: {format_time(total_duration)}")
    print(f"Average Time per Target: {format_time(summary.get('avg_time_seconds', 0))}")
    
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
            
            time_text = f" [{format_time(target.get('time_seconds', 0))}]"
            print(f"  {i}. {target['company_name']} - Fit: {target['fit_level']} ({target['fit_score']:.2f}){signals_text}{time_text}")


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
    
    # Add pagination and sorting parameters
    if args.limit is not None:
        filters["limit"] = args.limit
    if args.offset > 0:
        filters["offset"] = args.offset
    if args.sort_by:
        filters["sort_by"] = args.sort_by
    if args.sort_order:
        filters["sort_order"] = args.sort_order
    
    # Report on filters being applied
    print("Filters applied:")
    if not filters:
        print("  None - showing all results")
    else:
        for k, v in filters.items():
            print(f"  {k}: {v}")
    
    # Run query
    results, total_count = db_manager.get_research_results(**filters)
    
    # Display results
    if not results:
        print("\nNo results match the specified filters.")
        return
    
    print(f"\nFound {len(results)} results (of {total_count} total matches):")
    
    # Show pagination info if applicable
    if args.limit is not None:
        start_idx = args.offset + 1
        end_idx = min(args.offset + len(results), total_count)
        print(f"Showing results {start_idx}-{end_idx} of {total_count}")
        
        # Show pagination controls if needed
        if total_count > args.limit:
            print("\nFor next page:")
            next_offset = args.offset + args.limit
            if next_offset < total_count:
                print(f"  --offset {next_offset} --limit {args.limit}")
            
            if args.offset > 0:
                prev_offset = max(0, args.offset - args.limit)
                print("For previous page:")
                print(f"  --offset {prev_offset} --limit {args.limit}")
    
    # Display results
    for i, result in enumerate(results, 1):
        time_text = f" [{format_time(result.get('total_time_seconds', 0))}]" if result.get('total_time_seconds', 0) > 0 else ""
        print(f"\n{i}. {result['company_name']}")
        print(f"   Website: {result['website']}")
        print(f"   Fit: {result['fit_level']} ({result['fit_score']:.2f}){time_text}")
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
    required_vars = ["GEMINI_API_TOKEN", "JINA_API_TOKEN"]
    
    # Add Apollo API key to required vars if using Apollo source
    if args.use_apollo:
        required_vars.append("APOLLO_ORG_SEARCH_API_KEY")
    
    # Check for missing vars
    for var in required_vars:
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
        from .utils import create_sample_selling_product
        product = create_sample_selling_product()
        print(f"Using sample product: {product.name}")
    else:
        product = create_selling_product_from_input()
    
    # Initialize LLM model for filter derivation if needed
    from .research_engine import ProspectingResearchEngine
    engine = ProspectingResearchEngine(selling_product=product, verbose=True, selling_product_research="")
    
    # Get target companies
    targets = []
    
    # Method 1: Use Apollo API for target company discovery
    if args.use_apollo:
        print("\n=== GENERATING TARGETS FROM APOLLO API ===")
        
        # Create filter params from args
        manual_filters = {}
        if args.industry and len(args.industry) > 0:
            # Make sure we have a non-empty list of industries
            industries = [ind for ind in args.industry if ind]
            if industries:
                manual_filters["industries"] = industries
        if args.employee_min:
            manual_filters["employee_count_min"] = args.employee_min
        if args.employee_max:
            manual_filters["employee_count_max"] = args.employee_max
        if args.countries:
            # Clean up country names by stripping whitespace
            countries = [country.strip() for country in args.countries.split(",") if country.strip()]
            if countries:
                manual_filters["countries"] = countries
        if args.keywords:
            manual_filters["keywords"] = args.keywords
            
        # Use filter template if specified
        filter_template = args.filter_template if hasattr(args, 'filter_template') else None
        
        # Set max companies with a minimum of 100 per page to ensure results
        max_companies = args.limit if hasattr(args, 'limit') and args.limit > 0 else APOLLO_API_CONFIG.get("default_max_companies", 100)
        # Ensure per_page is at least 100 to get results from Apollo
        max_companies = max(max_companies, 100)
        
        # Generate targets from Apollo
        targets = asyncio.run(generate_targets_from_apollo(
            product=product,
            model=engine.llm,
            max_companies=max_companies,
            manual_filters=manual_filters if manual_filters else None,
            filter_template=filter_template,
            use_ai_filters=args.ai_filters,
            interactive=args.interactive,
            include_filter_explanation=True
        ))
        
        if not targets:
            print("No target companies found through Apollo API. Please adjust filters or use CSV input.")
            return
    
    # Method 2: Use CSV file
    elif args.csv:
        # Add additional arguments for CSV processing
        csv_offset = args.offset if hasattr(args, 'offset') and args.offset > 0 else 0
        csv_limit = args.limit if hasattr(args, 'limit') and args.limit > 0 else 0
        
        targets = load_targets_from_csv(args.csv, limit=csv_limit, offset=csv_offset)
        
        if csv_offset > 0 or csv_limit > 0:
            print(f"Loaded {len(targets)} targets from {args.csv} (offset={csv_offset}, limit={csv_limit if csv_limit > 0 else 'all'})")
        else:
            print(f"Loaded {len(targets)} targets from {args.csv}")
    
    # Method 3: Single manual target
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
            asyncio.run(batch_research_targets(targets, product, args.output, 0, db_manager))
    finally:
        # Always close database connection
        db_manager.close()


def main():
    """Main entry point."""
    # Load environment variables from .env file if it exists
    # Check both current directory and the script's directory
    env_locations = ['.env', os.path.join(os.path.dirname(__file__), '.env')]
    for env_path in env_locations:
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            os.environ[key] = value
            break  # Found and loaded, stop looking
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Deep Research Prospecting Tool")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Create a shared parent parser for common options
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--output", type=str, default="deep_research_results", help="Directory to save research results")
    common_parser.add_argument("--db", type=str, default="deep_research.db", help="Database file path")
    common_parser.add_argument("--use-sqlite", action="store_true", help="Use SQLite instead of DuckDB (if available)")
    common_parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    # Add research-single subcommand
    single_parser = subparsers.add_parser('research-single', parents=[common_parser],
                                         help='Research a single target company')
    single_parser.add_argument("--selling-product", required=True, 
                              help="Name of the product you're selling")
    single_parser.add_argument("--selling-website", required=True, 
                              help="Website of the product you're selling")
    single_parser.add_argument("--target-name", required=True, 
                              help="Name of the target company")
    single_parser.add_argument("--target-website", required=True, 
                              help="Website of the target company")
    single_parser.add_argument("--target-industry", default="", 
                              help="Industry of the target company")
    
    # Add batch-research subcommand
    batch_parser = subparsers.add_parser('batch-research', parents=[common_parser],
                                        help='Research multiple targets from a CSV file')
    batch_parser.add_argument("--selling-product", required=True, 
                             help="Name of the product you're selling")
    batch_parser.add_argument("--selling-website", required=True, 
                             help="Website of the product you're selling")
    batch_parser.add_argument("--targets-csv", required=True, 
                             help="Path to CSV file with target companies")
    batch_parser.add_argument("--limit", type=int, default=0, 
                             help="Limit the number of targets to process (0 for all)")
    batch_parser.add_argument("--offset", type=int, default=0, 
                             help="Skip this many targets from the beginning")
    
    # Keep the original interface as default behavior (for backwards compatibility)
    parser.add_argument("--csv", type=str, default="", help="Path to CSV file with target companies")
    parser.add_argument("--output", type=str, default="deep_research_results", help="Directory to save research results")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of targets to process (0 for all)")
    parser.add_argument("--offset", type=int, default=0, help="Skip this many targets from the beginning of CSV")
    parser.add_argument("--sample-product", action="store_true", help="Use a sample product definition for testing")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--db", type=str, default="deep_research.db", help="Database file path")
    parser.add_argument("--use-sqlite", action="store_true", help="Use SQLite instead of DuckDB (if available)")
    parser.add_argument("--query", action="store_true", help="Query mode - search existing results instead of running research")
    
    # Query mode options
    query_group = parser.add_argument_group('Query mode options')
    query_group.add_argument("--company", type=str, default="", help="Filter by company name in query mode")
    query_group.add_argument("--signal", type=str, default="", help="Filter by signal name in query mode")
    query_group.add_argument("--min-score", type=float, default=None, help="Filter by minimum fit score in query mode")
    query_group.add_argument("--sort-by", type=str, default="fit_score", 
                       help="Field to sort by in query mode (fit_score, company_name, timestamp, total_time_seconds)")
    query_group.add_argument("--sort-order", type=str, default="DESC", help="Sort order in query mode (ASC or DESC)")
    
    # Apollo API options
    apollo_group = parser.add_argument_group('Apollo API options')
    apollo_group.add_argument("--use-apollo", action="store_true", help="Use Apollo API to find target companies")
    apollo_group.add_argument("--industry", type=str, default=None, help="Filter by industry when using Apollo (can be used multiple times)", action="append")
    apollo_group.add_argument("--employee-min", type=int, default=None, help="Minimum employee count filter for Apollo")
    apollo_group.add_argument("--employee-max", type=int, default=None, help="Maximum employee count filter for Apollo")
    apollo_group.add_argument("--countries", type=str, default="", 
                        help="Comma-separated list of countries to filter by (e.g. 'United States,Canada')")
    apollo_group.add_argument("--keywords", type=str, default="", 
                        help="Keywords to search for in Apollo (e.g. 'cloud security compliance')")
    apollo_group.add_argument("--filter-template", type=str, default="", 
                        choices=list(COMMON_FILTER_TEMPLATES.keys()), 
                        help="Use a predefined filter template (e.g. b2b_saas, enterprise)")
    apollo_group.add_argument("--ai-filters", action="store_true", default=True, 
                        help="Use AI to derive optimal filters from product information")
    apollo_group.add_argument("--no-ai-filters", action="store_false", dest="ai_filters",
                        help="Disable AI-derived filters")
    apollo_group.add_argument("--interactive", action="store_true",
                        help="Interactively confirm and edit AI-derived filters")
    
    args = parser.parse_args()
    
    # Handle subcommands
    if args.command == 'research-single':
        # Create SellingProduct
        product = SellingProduct(
            name=args.selling_product,
            website=args.selling_website
        )
        
        # Create ProspectingTarget
        target = ProspectingTarget(
            company_name=args.target_name,
            website=args.target_website,
            industry=args.target_industry
        )
        
        # Set up database
        db_manager = DatabaseManager(args.db, use_duckdb=not args.use_sqlite)
        
        try:
            asyncio.run(research_single_target(target, product, args.output, db_manager))
        finally:
            db_manager.close()
            
    elif args.command == 'batch-research':
        # Create SellingProduct
        product = SellingProduct(
            name=args.selling_product,
            website=args.selling_website
        )
        
        # Load targets from CSV
        targets = load_targets_from_csv(args.targets_csv)
        
        # Apply limit and offset if specified
        if args.offset > 0:
            targets = targets[args.offset:]
        if args.limit > 0:
            targets = targets[:args.limit]
        
        # Set up database
        db_manager = DatabaseManager(args.db, use_duckdb=not args.use_sqlite)
        
        try:
            asyncio.run(batch_research_targets(targets, product, args.output, args.offset, db_manager))
        finally:
            db_manager.close()
    else:
        # Original behavior for backwards compatibility
        db_manager = DatabaseManager(args.db, use_duckdb=not args.use_sqlite)
        
        # Query mode - search existing results
        if args.query:
            return run_query_mode(db_manager, args)
        
        # Research mode - run new research
        return run_research_mode(db_manager, args)


if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utility functions for the deep research prospecting tool.
"""

import pandas as pd
from typing import List

from .data_models import ProspectingTarget


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


def format_time(seconds: float) -> str:
    if seconds is None:
        return "0.0 seconds"
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"


def get_highest_scoring_targets(results: List[dict], top_n: int = 10) -> List[dict]:
    sorted_results = sorted(results, key=lambda x: float(x.get('fit_score', 0)), reverse=True)
    return sorted_results[:top_n]


def create_sample_selling_product() -> 'SellingProduct':
    """Create a sample SellingProduct for testing."""
    from .data_models import SellingProduct
    return SellingProduct(
        name="Example Product",
        website="https://www.example.com",
        description="An example product for testing"
    )
"""
Example scripts demonstrating common use cases for the technology enrichment feature.
These examples show how to use the API for various technology enrichment scenarios.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TechnologyEnrichmentExamples:
    def __init__(self, api_base_url: str = "http://localhost:8000/api/v1"):
        self.api_base_url = api_base_url

    async def enrich_single_account(self, account_id: str, website: str) -> Dict[str, Any]:
        """
        Enrich a single account with technology data.
        
        Args:
            account_id: The ID of the account to enrich
            website: The website URL to analyze
            
        Returns:
            Dict containing the enrichment results
        """
        # Create enrichment task
        response = requests.post(
            f"{self.api_base_url}/tasks/create/technology_enrichment_builtwith",
            json={
                "account_id": account_id,
                "account_data": {
                    "website": website
                }
            }
        )
        response.raise_for_status()
        job_id = response.json()["job_id"]
        
        # Poll for completion
        while True:
            status_response = requests.get(f"{self.api_base_url}/tasks/{job_id}/status")
            status_data = status_response.json()
            
            if status_data["status"] in ["completed", "failed"]:
                return status_data
            
            await asyncio.sleep(5)  # Wait 5 seconds before checking again

    async def bulk_enrich_accounts(
        self,
        accounts: List[Dict[str, str]],
        max_concurrent: int = 5
    ) -> Dict[str, Any]:
        """
        Enrich multiple accounts concurrently.
        
        Args:
            accounts: List of dicts with account_id and website
            max_concurrent: Maximum number of concurrent enrichments
            
        Returns:
            Dict containing results for all accounts
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = {}

        async def enrich_with_semaphore(account: Dict[str, str]):
            async with semaphore:
                result = await self.enrich_single_account(
                    account["account_id"],
                    account["website"]
                )
                results[account["account_id"]] = result

        tasks = [
            enrich_with_semaphore(account)
            for account in accounts
        ]
        await asyncio.gather(*tasks)
        return results

    async def find_accounts_using_technology(
        self,
        technology: str,
        min_confidence: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find all accounts using a specific technology.
        
        Args:
            technology: The technology to search for
            min_confidence: Minimum confidence score (0-1)
            
        Returns:
            List of accounts using the technology
        """
        # Note: This assumes you have a way to list accounts
        # You would need to implement get_all_accounts() based on your system
        accounts = await self.get_all_accounts()
        matching_accounts = []

        for account in accounts:
            status_response = requests.get(
                f"{self.api_base_url}/tasks/{account['last_enrichment_job_id']}/status"
            )
            enrichment_data = status_response.json()
            
            if enrichment_data["status"] != "completed":
                continue
                
            tech_data = enrichment_data["processed_data"]["technology_data"]
            if (
                technology in tech_data["technologies"] and
                tech_data["confidence_scores"][technology] >= min_confidence
            ):
                matching_accounts.append({
                    "account_id": account["id"],
                    "website": account["website"],
                    "confidence": tech_data["confidence_scores"][technology]
                })
        
        return matching_accounts

    async def monitor_technology_changes(
        self,
        account_id: str,
        website: str,
        interval_days: int = 30
    ) -> Dict[str, Any]:
        """
        Monitor an account for technology stack changes.
        
        Args:
            account_id: The ID of the account to monitor
            website: The website URL to analyze
            interval_days: How often to check for changes
            
        Returns:
            Dict containing any detected changes
        """
        # Get current technology data
        current_result = await self.enrich_single_account(account_id, website)
        if current_result["status"] != "completed":
            raise Exception(f"Failed to get current technology data: {current_result}")
            
        current_tech = current_result["processed_data"]["technology_data"]
        
        # Get previous technology data (if exists)
        previous_response = requests.get(
            f"{self.api_base_url}/tasks/{account_id}/previous_enrichment",
            params={"enrichment_type": "technology_info"}
        )
        
        if previous_response.status_code == 404:
            return {"message": "No previous data available for comparison"}
            
        previous_tech = previous_response.json()["processed_data"]["technology_data"]
        
        # Compare and find changes
        added_tech = set(current_tech["technologies"]) - set(previous_tech["technologies"])
        removed_tech = set(previous_tech["technologies"]) - set(current_tech["technologies"])
        
        return {
            "added_technologies": list(added_tech),
            "removed_technologies": list(removed_tech),
            "comparison_date": previous_response.json()["timestamp"]
        }

async def main():
    """Example usage of the TechnologyEnrichmentExamples class."""
    examples = TechnologyEnrichmentExamples()
    
    # Example 1: Enrich a single account
    result = await examples.enrich_single_account(
        "test-account-1",
        "https://example.com"
    )
    logger.info(f"Single account enrichment result: {json.dumps(result, indent=2)}")
    
    # Example 2: Bulk enrich multiple accounts
    accounts = [
        {"account_id": "test-account-2", "website": "https://example2.com"},
        {"account_id": "test-account-3", "website": "https://example3.com"}
    ]
    bulk_results = await examples.bulk_enrich_accounts(accounts)
    logger.info(f"Bulk enrichment results: {json.dumps(bulk_results, indent=2)}")
    
    # Example 3: Find accounts using React
    react_accounts = await examples.find_accounts_using_technology("React")
    logger.info(f"Accounts using React: {json.dumps(react_accounts, indent=2)}")
    
    # Example 4: Monitor technology changes
    changes = await examples.monitor_technology_changes(
        "test-account-1",
        "https://example.com"
    )
    logger.info(f"Technology changes: {json.dumps(changes, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())
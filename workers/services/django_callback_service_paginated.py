import logging
import math
from typing import Dict, Any, Optional
import httpx

from utils.retry_utils import RetryConfig, RetryableError, with_retry, RETRYABLE_STATUS_CODES
from typing import Dict, Any, List
import logging
import math
from typing import Dict, Any, Optional

import httpx

from utils.retry_utils import RetryConfig, RetryableError, with_retry, RETRYABLE_STATUS_CODES

logger = logging.getLogger(__name__)


class PaginatedCallbackService:
    """Service for handling paginated callbacks with backward compatibility."""
    LEADS_PER_PAGE = 20

    CALLBACK_RETRY_CONFIG = RetryConfig(
        max_attempts=5,
        base_delay=1.0,
        max_delay=30.0,
        retryable_exceptions=[
            RetryableError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
            httpx.TransportError,
            httpx.RequestError
        ]
    )

    def __init__(self, callback_service, connection_pool):
        """Initialize with existing callback service for auth handling."""
        self.callback_service = callback_service
        self.django_base_url = callback_service.django_base_url
        self.callback_path = callback_service.callback_path
        self.pool = connection_pool

    def _should_paginate(self, data: Dict[str, Any]) -> bool:
        """Determine if payload needs pagination based on size."""
        try:
            processed_data = data.get('processed_data', {})
            # Check both types of leads without mutating data
            qualified_leads = processed_data.get('qualified_leads', [])
            structured_leads = processed_data.get('structured_leads', [])

            # Use the longer list to determine pagination
            max_leads = max(len(qualified_leads), len(structured_leads))
            return max_leads > self.LEADS_PER_PAGE

        except Exception as e:
            logger.warning(f"Error checking payload size: {e}")
            return False

    def _paginate_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Split data into ID-aligned chunks."""
        pages = []

        # Create copies to avoid mutating the original
        raw_data = data.get('raw_data', {})
        processed_data = data.get('processed_data', {}).copy()

        qualified_leads = processed_data.get('qualified_leads', [])
        structured_leads = processed_data.get('structured_leads', [])
        all_leads = processed_data.get('all_leads', [])

        # Build dictionaries keyed by lead ID for quick access
        qualified_dict = {lead['id']: lead for lead in qualified_leads}
        structured_dict = {lead['id']: lead for lead in structured_leads}
        all_dict = {lead['id']: lead for lead in all_leads}

        all_ids_ordered = [lead['id'] for lead in all_leads]

        all_ids_set = set(all_ids_ordered)
        for lead in qualified_leads:
            if lead['id'] not in all_ids_set:
                all_ids_ordered.append(lead['id'])
                all_ids_set.add(lead['id'])

        for lead in structured_leads:
            if lead['id'] not in all_ids_set:
                all_ids_ordered.append(lead['id'])
                all_ids_set.add(lead['id'])

        # Now we have a canonical list of IDs in the final desired order
        max_leads = len(all_ids_ordered)
        total_pages = math.ceil(max_leads / self.LEADS_PER_PAGE)

        # --- Split the ID list into pages ---
        for page_num in range(total_pages):
            start_idx = page_num * self.LEADS_PER_PAGE
            end_idx = start_idx + self.LEADS_PER_PAGE
            chunk_ids = all_ids_ordered[start_idx:end_idx]

            # Collect the leads (by matching ID) for each category
            paged_qualified_leads = []
            paged_structured_leads = []
            paged_all_leads = []

            for lead_id in chunk_ids:
                if lead_id in qualified_dict:
                    paged_qualified_leads.append(qualified_dict[lead_id])
                if lead_id in structured_dict:
                    paged_structured_leads.append(structured_dict[lead_id])
                if lead_id in all_dict:
                    paged_all_leads.append(all_dict[lead_id])

            # Build the new processed_data for this page
            page_processed_data = processed_data.copy()
            page_processed_data.update({
                'qualified_leads': paged_qualified_leads,
                'structured_leads': paged_structured_leads,
                'all_leads': paged_all_leads
            })

            # Build the final page data
            page_data = data.copy()
            page_data['processed_data'] = page_processed_data
            page_data['pagination'] = {
                'page': page_num + 1,
                'total_pages': total_pages,
                'leads_per_page': self.LEADS_PER_PAGE,
                'total_leads': max_leads,
                'current_chunk': {
                    'qualified_leads': len(paged_qualified_leads),
                    'structured_leads': len(paged_structured_leads),
                    'all_leads': len(paged_all_leads)
                }
            }
            # Make sure trace_id is included in paginated data if present
            if 'trace_id' in data:
                page_data['trace_id'] = data['trace_id']

            pages.append(page_data)

        return pages

    @with_retry(retry_config=CALLBACK_RETRY_CONFIG, operation_name="send_paginated_callback")
    async def _send_single_callback(self, callback_data: Dict[str, Any]) -> bool:
        """Send a single callback with retry logic."""
        try:
            id_token = await self.callback_service.get_id_token()
            callback_url = f"{self.django_base_url}{self.callback_path}"

            async with self.pool.acquire_connection() as client:
                response = await client.post(
                    callback_url,
                    json=callback_data,
                    headers={
                        "Authorization": f"Bearer {id_token}",
                        "Content-Type": "application/json"
                    },
                    timeout=300.0
                )

                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise RetryableError(f"Retryable status code {response.status_code}")

                response.raise_for_status()
                return True

        except Exception as e:
            logger.error(f"Error sending callback: {str(e)}")
            raise

    async def send_callback(
            self,
            job_id: str,
            account_id: str,
            status: str,
            enrichment_type: str = 'company_info',
            lead_id: str = None,
            raw_data: Optional[Dict[str, Any]] = None,
            processed_data: Optional[Dict[str, Any]] = None,
            error_details: Optional[Dict[str, Any]] = None,
            source: str = 'jina_ai',
            is_partial: bool = False,
            completion_percentage: int = 100,
            attempt_number: Optional[int] = None,
            max_retries: Optional[int] = None,
            trace_id: Optional[str] = None
    ) -> bool:
        """Send callback with automatic pagination if needed."""
        callback_data = {
            "job_id": job_id,
            "account_id": account_id,
            "lead_id": lead_id,
            "status": status,
            "enrichment_type": enrichment_type,
            "source": source,
            "is_partial": is_partial,
            "completion_percentage": completion_percentage,
            "raw_data": raw_data,
            "processed_data": processed_data,
            "error_details": error_details,
            "attempt_number": attempt_number,
            "max_retries": max_retries
        }
        
        # Add trace_id if provided
        if trace_id is not None:
            callback_data["trace_id"] = trace_id

        try:
            if not self._should_paginate(callback_data):
                # Use existing callback service for backward compatibility
                return await self.callback_service.send_callback(
                    job_id=job_id,
                    account_id=account_id,
                    status=status,
                    enrichment_type=enrichment_type,
                    lead_id=lead_id,
                    raw_data=raw_data,
                    processed_data=processed_data,
                    error_details=error_details,
                    source=source,
                    is_partial=is_partial,
                    completion_percentage=completion_percentage,
                    attempt_number=attempt_number,
                    max_retries=max_retries,
                    trace_id=trace_id
                )

            # Handle paginated case
            pages = self._paginate_data(callback_data)
            total_pages = len(pages)

            for i, page in enumerate(pages):
                # Update status for intermediate pages
                # if i < total_pages:
                #     page['status'] = 'completed'
                #     page['is_partial'] = True
                #     page['completion_percentage'] = int((i / total_pages) * 100)

                success = await self._send_single_callback(page)
                if not success:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error in paginated callback: {str(e)}")
            return False

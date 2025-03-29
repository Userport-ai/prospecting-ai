"""
Utility functions for custom column operations.

This module provides reusable functions for context gathering, preparing values,
and triggering custom column value generation that can be used by both
AccountsViewSet, LeadsViewSet, and CustomColumnViewSet.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from django.db import transaction

from app.models import Lead, Account
from app.models.custom_column import (
    CustomColumn, AccountCustomColumnValue, LeadCustomColumnValue
)
from app.services.worker_service import WorkerService

logger = logging.getLogger(__name__)


def get_batch_custom_column_values(entity_type: str, entity_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get custom column values for multiple entities in a batch with LLM-friendly formatting.

    Args:
        entity_type: Either CustomColumn.EntityType.LEAD or CustomColumn.EntityType.ACCOUNT
        entity_ids: List of entity IDs

    Returns:
        dict: Dictionary mapping entity_id -> {column_name -> column_data}
    """
    result = {entity_id: {} for entity_id in entity_ids}

    try:
        if entity_type == CustomColumn.EntityType.LEAD:
            column_values = LeadCustomColumnValue.objects.filter(
                lead_id__in=entity_ids,
                status=LeadCustomColumnValue.Status.COMPLETED
            ).select_related('column')

            for cv in column_values:
                # Extract value based on column type
                if cv.value_string is not None:
                    value = cv.value_string
                elif cv.value_json is not None:
                    value = cv.value_json
                elif cv.value_boolean is not None:
                    value = cv.value_boolean
                elif cv.value_number is not None:
                    value = cv.value_number
                else:
                    continue

                # Format for better LLM understanding
                entity_id = str(cv.lead_id)
                if entity_id not in result:
                    result[entity_id] = {}

                # Use column name as the key instead of ID
                column_name = cv.column.name
                result[entity_id][column_name] = {
                    'value': value,
                    'description': cv.column.description or f"Value for {column_name}",
                    'question': cv.column.question,
                    'type': cv.column.response_type
                }

        else:  # Account entity type
            column_values = AccountCustomColumnValue.objects.filter(
                account_id__in=entity_ids,
                status=AccountCustomColumnValue.Status.COMPLETED
            ).select_related('column')

            for cv in column_values:
                # Extract value based on column type
                if cv.value_string is not None:
                    value = cv.value_string
                elif cv.value_json is not None:
                    value = cv.value_json
                elif cv.value_boolean is not None:
                    value = cv.value_boolean
                elif cv.value_number is not None:
                    value = cv.value_number
                else:
                    continue

                # Format for better LLM understanding
                entity_id = str(cv.account_id)
                if entity_id not in result:
                    result[entity_id] = {}

                # Use column name as the key instead of ID
                column_name = cv.column.name
                result[entity_id][column_name] = {
                    'value': value,
                    'description': cv.column.description or f"Value for {column_name}",
                    'question': cv.column.question,
                    'type': cv.column.response_type
                }
    except Exception as e:
        logger.error(f"Error getting batch custom column values: {str(e)}", exc_info=True)

    return result


def get_batch_account_custom_column_values_for_leads(lead_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get account custom column values for leads in a batch with LLM-friendly formatting.

    Args:
        lead_ids: List of lead IDs

    Returns:
        dict: Dictionary mapping lead_id -> account custom column values
    """
    result = {lead_id: {} for lead_id in lead_ids}

    try:
        # First, get all the account IDs for these leads
        lead_to_account_map = {}
        account_ids = set()

        leads = Lead.objects.filter(id__in=lead_ids).values('id', 'account_id')
        for lead in leads:
            if lead['account_id']:
                lead_to_account_map[str(lead['id'])] = str(lead['account_id'])
                account_ids.add(str(lead['account_id']))

        if not account_ids:
            return result

        # Get account custom column values
        account_column_values = get_batch_custom_column_values(
            CustomColumn.EntityType.ACCOUNT,
            list(account_ids)
        )

        # Map account custom column values to leads
        for lead_id, account_id in lead_to_account_map.items():
            if account_id in account_column_values:
                result[lead_id] = account_column_values[account_id]

    except Exception as e:
        logger.error(f"Error getting account custom column values for leads: {str(e)}", exc_info=True)

    return result


def get_entity_context_data(
        tenant_id: str,
        custom_column: CustomColumn,
        entity_ids: List[str]
) -> Dict[str, Dict[str, Any]]:
    """
    Get comprehensive context data for entities to be used in column value generation.
    This function captures ALL available context exactly as the CustomColumnViewSet does.

    Args:
        tenant_id: The tenant ID
        custom_column: The CustomColumn instance
        entity_ids: List of entity IDs

    Returns:
        dict: Dictionary with entity_ids as keys and their context data as values
    """
    context_data = {}
    entity_type = custom_column.entity_type

    try:
        # Create empty context for each entity to ensure they all have entries
        for entity_id in entity_ids:
            context_data[entity_id] = {}

        # For each entity, gather all available context data
        if entity_type == CustomColumn.EntityType.LEAD:
            # Fetch lead data with related account information
            leads = Lead.objects.filter(
                id__in=entity_ids,
                tenant_id=tenant_id
            ).select_related('account', 'account__product')

            for lead in leads:
                lead_context = {}

                # Complete lead information
                lead_context['lead_info'] = {
                    'id': str(lead.id),
                    'name': f"{lead.first_name or ''} {lead.last_name or ''}".strip(),
                    'first_name': lead.first_name,
                    'last_name': lead.last_name,
                    'role_title': lead.role_title,
                    'linkedin_url': lead.linkedin_url,
                    'email': lead.email,
                    'phone': lead.phone,
                    'enrichment_status': lead.enrichment_status,
                    'score': lead.score,
                    'last_enriched_at': lead.last_enriched_at.isoformat() if lead.last_enriched_at else None,
                    'source': lead.source,
                    'suggestion_status': lead.suggestion_status,
                    'custom_fields': lead.custom_fields or {},
                    'created_at': lead.created_at.isoformat() if lead.created_at else None
                }

                # Company context (if lead has an associated account)
                if lead.account:
                    account = lead.account
                    lead_context['company'] = {
                        'id': str(account.id),
                        'name': account.name,
                        'website': account.website,
                        'linkedin_url': account.linkedin_url,
                        'industry': account.industry,
                        'location': account.location,
                        'employee_count': account.employee_count,
                        'company_type': account.company_type,
                        'founded_year': account.founded_year,
                        'customers': account.customers or [],
                        'competitors': account.competitors or [],
                        'technologies': account.technologies or {},
                        'funding_details': account.funding_details or {},
                        'custom_fields': account.custom_fields or {},
                        'recent_events': account.recent_events or []
                    }

                    # Add product info if available
                    if account.product:
                        product = account.product
                        lead_context['product'] = {
                            'id': str(product.id),
                            'name': product.name,
                            'description': product.description,
                            'icp_description': getattr(product, 'icp_description', None),
                            'persona_role_titles': getattr(product, 'persona_role_titles', {}),
                            'keywords': getattr(product, 'keywords', []),
                            'website': getattr(product, 'website', None),
                            'playbook_description': getattr(product, 'playbook_description', None)
                        }

                # LinkedIn activity data and enrichment insights
                if lead.enrichment_data:
                    # Extract LinkedIn activity if available
                    linkedin_activity = lead.enrichment_data.get('linkedin_activity', {})
                    if linkedin_activity:
                        lead_context['linkedin_activity'] = linkedin_activity

                    # Include personality insights if available
                    personality_insights = lead.enrichment_data.get('personality_insights', {})
                    if personality_insights:
                        lead_context['personality_insights'] = personality_insights

                    # Include any other enrichment data
                    for key, value in lead.enrichment_data.items():
                        if key not in ['linkedin_activity', 'personality_insights']:
                            lead_context[f'enrichment_{key}'] = value

                context_data[str(lead.id)] = lead_context

        else:  # Account entity type
            # Fetch accounts with related product
            accounts = Account.objects.filter(
                id__in=entity_ids,
                tenant_id=tenant_id
            ).select_related('product').prefetch_related('enrichment_statuses')

            for account in accounts:
                account_context = {}

                # Complete account information
                account_context['account_info'] = {
                    'id': str(account.id),
                    'name': account.name,
                    'website': account.website,
                    'linkedin_url': account.linkedin_url,
                    'industry': account.industry,
                    'location': account.location,
                    'employee_count': account.employee_count,
                    'company_type': account.company_type,
                    'founded_year': account.founded_year,
                    'customers': account.customers or [],
                    'competitors': account.competitors or [],
                    'last_enriched_at': account.last_enriched_at.isoformat() if account.last_enriched_at else None,
                    'custom_fields': account.custom_fields or {},
                    'settings': account.settings or {},
                    'created_at': account.created_at.isoformat() if account.created_at else None
                }

                # Include all available detailed information
                if account.technologies:
                    account_context['technologies'] = account.technologies

                if account.full_technology_profile:
                    account_context['full_technology_profile'] = account.full_technology_profile

                if account.funding_details:
                    account_context['funding_details'] = account.funding_details

                if account.enrichment_sources:
                    account_context['enrichment_sources'] = account.enrichment_sources

                if account.recent_events:
                    account_context['recent_events'] = account.recent_events

                # Try to get enrichment summary if it has related data
                try:
                    enrichment_summary = account.get_enrichment_summary()
                    if enrichment_summary:
                        account_context['enrichment_summary'] = {k: v for k, v in enrichment_summary.items()
                                                                 if (k != 'statuses' and k != 'last_update')}  # Exclude statuses objects
                except Exception as e:
                    logger.error(f"Error getting enrichment summary: {str(e)}")

                # Add product info if available
                if account.product:
                    product = account.product
                    account_context['product'] = {
                        'id': str(product.id),
                        'name': product.name,
                        'description': product.description,
                        'icp_description': getattr(product, 'icp_description', None),
                        'persona_role_titles': getattr(product, 'persona_role_titles', {}),
                        'keywords': getattr(product, 'keywords', []),
                        'website': getattr(product, 'website', None),
                        'playbook_description': getattr(product, 'playbook_description', None)
                    }

                # Get related leads count (to understand account size in the system)
                try:
                    leads_count = Lead.objects.filter(account_id=account.id).count()
                    account_context['leads_count'] = leads_count
                except Exception as e:
                    logger.error(f"Error getting leads count: {str(e)}")

                context_data[str(account.id)] = account_context

        # Get custom column values in batch for all entities
        custom_column_values_batch = get_batch_custom_column_values(entity_type, entity_ids)

        # Add to each entity's context
        for entity_id in entity_ids:
            str_entity_id = str(entity_id)
            if str_entity_id in custom_column_values_batch and custom_column_values_batch[str_entity_id]:
                if str_entity_id in context_data:
                    context_data[str_entity_id]['insights'] = custom_column_values_batch[str_entity_id]

        # For lead entities, also get the account custom column values
        if entity_type == CustomColumn.EntityType.LEAD:
            account_column_values_for_leads = get_batch_account_custom_column_values_for_leads(entity_ids)

            # Add account column values to lead context
            for lead_id in entity_ids:
                str_lead_id = str(lead_id)
                if str_lead_id in account_column_values_for_leads and account_column_values_for_leads[str_lead_id]:
                    if str_lead_id in context_data:
                        context_data[str_lead_id]['company_insights'] = account_column_values_for_leads[str_lead_id]

        return context_data

    except Exception as e:
        logger.error(f"Error getting context data: {str(e)}", exc_info=True)
        # Return an empty context for all entities to avoid failures
        return {entity_id: {} for entity_id in entity_ids}


def prepare_lead_values(tenant_id: str, custom_column: CustomColumn, lead_ids: List[str]) -> None:
    """
    Create or update pending lead column values.

    Args:
        tenant_id: The tenant ID
        custom_column: The CustomColumn instance
        lead_ids: List of lead IDs
    """
    with transaction.atomic():
        for lead_id in lead_ids:
            LeadCustomColumnValue.objects.update_or_create(
                column=custom_column,
                lead_id=lead_id,
                defaults={
                    'status': LeadCustomColumnValue.Status.PROCESSING,
                    'tenant_id': tenant_id
                }
            )


def prepare_account_values(tenant_id: str, custom_column: CustomColumn, account_ids: List[str]) -> None:
    """
    Create or update pending account column values.

    Args:
        tenant_id: The tenant ID
        custom_column: The CustomColumn instance
        account_ids: List of account IDs
    """
    with transaction.atomic():
        for account_id in account_ids:
            AccountCustomColumnValue.objects.update_or_create(
                column=custom_column,
                account_id=account_id,
                defaults={
                    'status': AccountCustomColumnValue.Status.PROCESSING,
                    'tenant_id': tenant_id
                }
            )


def get_column_config(custom_column: CustomColumn) -> Dict[str, Any]:
    """
    Get a standardized configuration object for a CustomColumn.

    Args:
        custom_column: The CustomColumn instance

    Returns:
        dict: Configuration object for the worker service
    """
    return {
        "id": str(custom_column.id),
        "name": custom_column.name,
        "description": custom_column.description or "",
        "question": custom_column.question,
        "response_type": custom_column.response_type,
        "response_config": custom_column.response_config,
        "examples": custom_column.response_config.get("examples", []),
        "validation_rules": custom_column.response_config.get("validation_rules", [])
    }


def trigger_custom_column_generation(
        tenant_id: str,
        column_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
        batch_size: int = 10  # Default batch size of 10
) -> List[Dict[str, Any]]:
    """
    Trigger custom column value generation for entity IDs with batching support.
    If column_id is provided, triggers generation for only that column.
    If entity_type is provided without column_id, triggers generation for all active columns of that type.

    Args:
        tenant_id: The tenant ID
        column_id: Optional specific column ID to generate values for
        entity_type: Either 'lead' or 'account' (required if column_id not provided)
        entity_ids: List of entity IDs to process
        request_id: Optional request ID for idempotency
        job_id: Optional job ID for tracking
        batch_size: Number of entities to process in each batch (default: 10)

    Returns:
        List of dictionaries with job information
    """
    worker_service = WorkerService()
    results = []

    # Validate parameters
    if not entity_ids:
        logger.error("No entity IDs provided for custom column generation")
        return [{"error": "No entity IDs provided"}]

    # If column_id is provided, get just that column
    if column_id:
        columns = CustomColumn.objects.filter(id=column_id, tenant_id=tenant_id)
    elif entity_type:
        # Get all active columns for the entity type
        columns = CustomColumn.objects.filter(
            tenant_id=tenant_id,
            entity_type=entity_type,
            is_active=True
        )
    else:
        logger.error("Either column_id or entity_type must be provided")
        return [{"error": "Either column_id or entity_type must be provided"}]

    # For each column, trigger generation
    for column in columns:
        column_results = []

        try:
            logger.info(f"Processing column {column.id} ({column.name}) for {len(entity_ids)} entities")

            # Create batches of entity IDs
            batch_count = 0
            total_batches = (len(entity_ids) + batch_size - 1) // batch_size  # Ceiling division

            for i in range(0, len(entity_ids), batch_size):
                batch_count += 1
                batch_ids = entity_ids[i:i + batch_size]

                # Create unique IDs for this batch if not provided
                batch_job_id = f"{job_id or str(uuid.uuid4())}_batch_{batch_count}"
                batch_request_id = f"{request_id or str(uuid.uuid4())}_batch_{batch_count}"

                logger.info(f"Processing batch {batch_count}/{total_batches} with {len(batch_ids)} entities")

                # Get column configuration
                column_config = get_column_config(column)

                # Get context data for this batch only
                context_data = get_entity_context_data(tenant_id, column, batch_ids)

                # Prepare entities for processing
                if column.entity_type == CustomColumn.EntityType.LEAD:
                    prepare_lead_values(tenant_id, column, batch_ids)
                else:
                    prepare_account_values(tenant_id, column, batch_ids)

                # Create payload for this batch
                payload = {
                    "column_id": str(column.id),
                    "entity_ids": batch_ids,
                    "column_config": column_config,
                    "context_data": context_data,
                    "tenant_id": tenant_id,
                    "batch_size": 10,  # Worker's internal batch size
                    "job_id": batch_job_id,
                    "concurrent_requests": 5,  # Worker's concurrency setting
                    "request_id": batch_request_id,
                    "batch_metadata": {
                        "batch_number": batch_count,
                        "total_batches": total_batches,
                        "parent_job_id": job_id or str(uuid.uuid4()),
                        "original_request_id": request_id or str(uuid.uuid4())
                    }
                }

                # Trigger worker task for this batch
                response = worker_service.trigger_custom_column_generation(payload)

                column_results.append({
                    "batch": batch_count,
                    "total_batches": total_batches,
                    "job_id": response.get("job_id", batch_job_id),
                    "entity_count": len(batch_ids),
                    "request_id": batch_request_id
                })

            # Add summary result for the column
            results.append({
                "column_id": str(column.id),
                "column_name": column.name,
                "entity_count": len(entity_ids),
                "batches": column_results,
                "parent_job_id": job_id or str(uuid.uuid4()),
                "parent_request_id": request_id or str(uuid.uuid4())
            })

        except Exception as e:
            logger.error(f"Error triggering column {column.id} generation: {str(e)}", exc_info=True)
            results.append({
                "column_id": str(column.id),
                "column_name": column.name,
                "error": str(e)
            })

    return results
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime

from fastapi.testclient import TestClient
from main import app
from models.technology_enrichment import (
    TechnologyProfile,
    QualityMetrics,
    EnrichmentResult,
    EnrichmentSummary,
    BuiltWithResponse
)

@pytest.fixture
def test_client():
    return TestClient(app)

@pytest.fixture
def mock_builtwith_response():
    return {
        "Domain": "example.com",
        "Results": [
            {
                "Result": [
                    {
                        "Name": "React",
                        "Categories": [{"Name": "JavaScript Frameworks"}],
                        "FirstDetected": "2023-01-01",
                        "LastDetected": "2024-01-01",
                        "Live": True,
                        "Paths": ["/", "/about"]
                    },
                    {
                        "Name": "Google Analytics",
                        "Categories": [{"Name": "Analytics"}],
                        "FirstDetected": "2023-01-01",
                        "LastDetected": "2024-01-01",
                        "Live": True,
                        "Paths": ["/"]
                    }
                ],
                "LastScan": "2024-01-01"
            }
        ]
    }

@pytest.fixture
def mock_callback_response():
    return {
        "status": "success",
        "message": "Callback processed successfully"
    }

@pytest.mark.asyncio
async def test_full_enrichment_flow(
    test_client,
    mock_builtwith_response,
    mock_callback_response
):
    """Test the complete flow of technology enrichment from API to callback."""
    
    with patch('services.builtwith_service.BuiltWithService.get_technology_profile') as mock_get_profile, \
         patch('services.django_callback_service.CallbackService.send_callback') as mock_callback, \
         patch('services.bigquery_service.BigQueryService.insert_enrichment_raw_data') as mock_bq:
        
        # Setup mocks
        mock_get_profile.return_value = TechnologyProfile(
            technologies=["React", "Google Analytics"],
            categories={
                "JavaScript Frameworks": ["React"],
                "Analytics": ["Google Analytics"]
            },
            confidence_scores={
                "React": 0.9,
                "Google Analytics": 0.8
            },
            meta={
                "domain": "example.com",
                "last_scan": "2024-01-01"
            }
        )
        mock_callback.return_value = mock_callback_response
        mock_bq.return_value = None

        # 1. Create task
        create_response = test_client.post(
            "/api/v1/tasks/create/technology_enrichment_builtwith",
            json={
                "account_id": "test-account",
                "account_data": {
                    "website": "https://example.com"
                },
                "job_id": "test-job"
            }
        )
        
        assert create_response.status_code == 200
        create_data = create_response.json()
        assert create_data["job_id"] == "test-job"

        # 2. Execute task
        execute_response = test_client.post(
            "/api/v1/tasks/technology_enrichment_builtwith",
            json={
                "account_id": "test-account",
                "account_data": {
                    "website": "https://example.com"
                },
                "job_id": "test-job"
            }
        )
        
        assert execute_response.status_code == 200
        execute_data = execute_response.json()
        assert execute_data["status"] == "completed"
        
        # Verify BuiltWith API was called
        mock_get_profile.assert_called_once()
        
        # Verify callbacks were sent (initial, progress, completion)
        assert mock_callback.call_count == 3
        
        # Verify data was stored in BigQuery
        mock_bq.assert_called_once()
        bq_call_args = mock_bq.call_args[1]
        assert bq_call_args["job_id"] == "test-job"
        assert bq_call_args["entity_id"] == "test-account"
        assert bq_call_args["source"] == "builtwith"
        
        # 3. Check task status
        status_response = test_client.get(f"/api/v1/tasks/test-job/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["status"] == "completed"

@pytest.mark.asyncio
async def test_enrichment_flow_with_errors(test_client):
    """Test error handling in the enrichment flow."""
    
    with patch('services.builtwith_service.BuiltWithService.get_technology_profile') as mock_get_profile, \
         patch('services.django_callback_service.CallbackService.send_callback') as mock_callback:
        
        # Setup mock to raise an error
        mock_get_profile.side_effect = Exception("API Error")
        
        # Execute task
        response = test_client.post(
            "/api/v1/tasks/technology_enrichment_builtwith",
            json={
                "account_id": "test-account",
                "account_data": {
                    "website": "https://example.com"
                },
                "job_id": "test-job"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert "API Error" in str(data["error"])
        
        # Verify error callback was sent
        mock_callback.assert_called()
        error_callback = mock_callback.call_args[1]
        assert error_callback["status"] == "failed"
        assert "API Error" in str(error_callback["error_details"]["message"])

@pytest.mark.asyncio
async def test_enrichment_flow_retry(test_client, mock_builtwith_response):
    """Test retrying a failed enrichment task."""
    
    # 1. Create a failed task
    with patch('services.builtwith_service.BuiltWithService.get_technology_profile') as mock_get_profile:
        mock_get_profile.side_effect = Exception("API Error")
        
        execute_response = test_client.post(
            "/api/v1/tasks/technology_enrichment_builtwith",
            json={
                "account_id": "test-account",
                "account_data": {
                    "website": "https://example.com"
                },
                "job_id": "test-job"
            }
        )
        
        assert execute_response.status_code == 200
        assert execute_response.json()["status"] == "failed"
    
    # 2. Retry the task
    with patch('services.builtwith_service.BuiltWithService.get_technology_profile') as mock_get_profile, \
         patch('services.django_callback_service.CallbackService.send_callback') as mock_callback:
        
        # Setup mock to succeed on retry
        mock_get_profile.return_value = TechnologyProfile(
            technologies=["React"],
            categories={"JavaScript Frameworks": ["React"]},
            confidence_scores={"React": 0.9},
            meta={"domain": "example.com", "last_scan": "2024-01-01"}
        )
        
        retry_response = test_client.post(f"/api/v1/tasks/test-job/retry")
        assert retry_response.status_code == 200
        
        # Execute retried task
        execute_response = test_client.post(
            "/api/v1/tasks/technology_enrichment_builtwith",
            json={
                "account_id": "test-account",
                "account_data": {
                    "website": "https://example.com"
                },
                "job_id": "test-job-retry",
                "attempt_number": 2
            }
        )
        
        assert execute_response.status_code == 200
        assert execute_response.json()["status"] == "completed"

@pytest.mark.asyncio
async def test_enrichment_flow_invalid_input(test_client):
    """Test handling of invalid input in the enrichment flow."""
    
    # Test missing website
    response = test_client.post(
        "/api/v1/tasks/create/technology_enrichment_builtwith",
        json={
            "account_id": "test-account",
            "account_data": {},  # Missing website
            "job_id": "test-job"
        }
    )
    
    assert response.status_code == 200  # Task is created but will fail
    
    # Execute task
    execute_response = test_client.post(
        "/api/v1/tasks/technology_enrichment_builtwith",
        json={
            "account_id": "test-account",
            "account_data": {},
            "job_id": "test-job"
        }
    )
    
    assert execute_response.status_code == 200
    data = execute_response.json()
    assert data["status"] == "failed"
    assert "website is required" in data["error"].lower()
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from tasks.technology_enrichment import TechnologyEnrichmentTask
from models.technology_enrichment import (
    TechnologyProfile,
    QualityMetrics,
    EnrichmentResult,
    EnrichmentSummary
)

@pytest.fixture
def mock_callback_service():
    return AsyncMock()

@pytest.fixture
def mock_bigquery_service():
    return AsyncMock()

@pytest.fixture
def mock_builtwith_service():
    return AsyncMock()

@pytest.fixture
async def technology_task(mock_callback_service):
    with patch('tasks.technology_enrichment.BigQueryService') as mock_bq, \
         patch('tasks.technology_enrichment.BuiltWithService') as mock_builtwith:
        task = TechnologyEnrichmentTask(mock_callback_service)
        task.bq_service = mock_bq()
        task.builtwith_service = mock_builtwith()
        return task

@pytest.fixture
def sample_technology_profile():
    return TechnologyProfile(
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

@pytest.mark.asyncio
async def test_create_task_payload(technology_task):
    # Arrange
    payload = {
        "account_id": "test-account",
        "account_data": {"website": "example.com"},
        "job_id": "test-job"
    }
    
    # Act
    result = await technology_task.create_task_payload(**payload)
    
    # Assert
    assert result["account_id"] == "test-account"
    assert result["account_data"]["website"] == "example.com"
    assert result["job_id"] == "test-job"

@pytest.mark.asyncio
async def test_create_task_payload_missing_fields(technology_task):
    # Act & Assert
    with pytest.raises(ValueError, match="Missing required fields"):
        await technology_task.create_task_payload(account_id="test-account")

@pytest.mark.asyncio
async def test_execute_success(technology_task, mock_callback_service, sample_technology_profile):
    # Arrange
    payload = {
        "account_id": "test-account",
        "account_data": {"website": "example.com"},
        "job_id": "test-job"
    }
    technology_task.builtwith_service.get_technology_profile.return_value = sample_technology_profile
    
    # Act
    result, summary = await technology_task.execute(payload)
    
    # Assert
    assert result["status"] == "completed"
    assert result["completion_percentage"] == 100
    assert summary["technologies_found"] == 2
    assert summary["categories_found"] == 2
    
    # Verify callbacks were sent
    assert mock_callback_service.send_callback.call_count == 3  # Initial, progress, and completion
    
    # Verify BigQuery storage
    assert technology_task.bq_service.insert_enrichment_raw_data.called

@pytest.mark.asyncio
async def test_execute_missing_website(technology_task):
    # Arrange
    payload = {
        "account_id": "test-account",
        "account_data": {},  # Missing website
        "job_id": "test-job"
    }
    
    # Act
    result, summary = await technology_task.execute(payload)
    
    # Assert
    assert summary["status"] == "failed"
    assert "website is required" in summary["error"].lower()

@pytest.mark.asyncio
async def test_calculate_quality_metrics_high_quality(technology_task, sample_technology_profile):
    # Act
    metrics = technology_task._calculate_quality_metrics(sample_technology_profile)
    
    # Assert
    assert isinstance(metrics, QualityMetrics)
    assert metrics.technology_count == 2
    assert metrics.category_count == 2
    assert metrics.average_confidence == 0.85  # (0.9 + 0.8) / 2
    assert metrics.detection_quality == "high"  # High due to count >= 2 and avg_confidence >= 0.7

@pytest.mark.asyncio
async def test_calculate_quality_metrics_empty_profile(technology_task):
    # Arrange
    empty_profile = TechnologyProfile()
    
    # Act
    metrics = technology_task._calculate_quality_metrics(empty_profile)
    
    # Assert
    assert isinstance(metrics, QualityMetrics)
    assert metrics.technology_count == 0
    assert metrics.category_count == 0
    assert metrics.average_confidence == 0.0
    assert metrics.detection_quality == "insufficient_data"

@pytest.mark.asyncio
async def test_execute_api_error(technology_task, mock_callback_service):
    # Arrange
    payload = {
        "account_id": "test-account",
        "account_data": {"website": "example.com"},
        "job_id": "test-job"
    }
    technology_task.builtwith_service.get_technology_profile.side_effect = Exception("API Error")
    
    # Act
    result, summary = await technology_task.execute(payload)
    
    # Assert
    assert summary["status"] == "failed"
    assert "API Error" in summary["error"]
    
    # Verify error callback was sent
    assert mock_callback_service.send_callback.called
    last_callback = mock_callback_service.send_callback.call_args[1]
    assert last_callback["status"] == "failed"
    assert "API Error" in str(last_callback["error_details"]["message"])

@pytest.mark.asyncio
async def test_enrichment_type_and_task_name(technology_task):
    # Assert
    assert technology_task.enrichment_type == "technology_info"
    assert technology_task.task_name == "technology_enrichment_builtwith"

@pytest.mark.asyncio
async def test_execute_with_invalid_domain(technology_task, mock_callback_service):
    # Arrange
    payload = {
        "account_id": "test-account",
        "account_data": {"website": "not-a-valid-url"},
        "job_id": "test-job"
    }
    
    # Act
    result, summary = await technology_task.execute(payload)
    
    # Assert
    assert summary["status"] == "failed"
    assert "domain" in summary["error"].lower()
    
    # Verify error callback was sent
    assert mock_callback_service.send_callback.called
    last_callback = mock_callback_service.send_callback.call_args[1]
    assert last_callback["status"] == "failed"
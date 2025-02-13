import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.builtwith_service import BuiltWithService
from models.technology_enrichment import BuiltWithResponse, TechnologyProfile

@pytest.fixture
def mock_cache_service():
    return AsyncMock()

@pytest.fixture
def builtwith_service(mock_cache_service):
    with patch.dict('os.environ', {'BUILTWITH_API_KEY': 'test-key'}):
        return BuiltWithService(mock_cache_service)

@pytest.fixture
def sample_api_response():
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

@pytest.mark.asyncio
async def test_get_technology_profile_success(builtwith_service, mock_cache_service, sample_api_response):
    # Arrange
    mock_cache_service.cached_request = AsyncMock(return_value=(sample_api_response, 200))
    
    # Act
    result = await builtwith_service.get_technology_profile("example.com")
    
    # Assert
    assert isinstance(result, TechnologyProfile)
    assert len(result.technologies) == 2
    assert "React" in result.technologies
    assert "Google Analytics" in result.technologies
    assert "JavaScript Frameworks" in result.categories
    assert "Analytics" in result.categories
    assert result.confidence_scores["React"] > 0.5
    assert result.meta["domain"] == "example.com"
    assert result.meta["last_scan"] == "2024-01-01"

@pytest.mark.asyncio
async def test_get_technology_profile_empty_response(builtwith_service, mock_cache_service):
    # Arrange
    empty_response = {"Domain": "example.com", "Results": []}
    mock_cache_service.cached_request = AsyncMock(return_value=(empty_response, 200))
    
    # Act
    result = await builtwith_service.get_technology_profile("example.com")
    
    # Assert
    assert isinstance(result, TechnologyProfile)
    assert len(result.technologies) == 0
    assert len(result.categories) == 0
    assert result.meta["domain"] == "example.com"
    assert result.meta["last_scan"] is None

@pytest.mark.asyncio
async def test_get_technology_profile_rate_limit(builtwith_service, mock_cache_service):
    # Arrange
    mock_cache_service.cached_request = AsyncMock(return_value=({}, 429))
    
    # Act & Assert
    with pytest.raises(RetryableError, match="Rate limit exceeded"):
        await builtwith_service.get_technology_profile("example.com")

@pytest.mark.asyncio
async def test_get_technology_profile_invalid_domain(builtwith_service):
    # Act & Assert
    with pytest.raises(ValueError, match="Domain is required"):
        await builtwith_service.get_technology_profile("")

@pytest.mark.asyncio
async def test_confidence_score_calculation(builtwith_service):
    # Arrange
    tech_data = BuiltWithResponse.Technology(
        Name="Test Tech",
        Categories=[{"Name": "Test Category"}],
        FirstDetected="2023-01-01",
        LastDetected="2024-01-01",
        Live=True,
        Paths=["/", "/about", "/contact"]
    )
    
    # Act
    score = builtwith_service._calculate_confidence_score(tech_data)
    
    # Assert
    assert 0 <= score <= 1
    assert score > 0.5  # Should be high confidence due to Live=True and multiple paths

@pytest.mark.asyncio
async def test_process_technology_data_with_invalid_data(builtwith_service):
    # Arrange
    invalid_response = {
        "Domain": "example.com",
        "Results": [
            {
                "Result": [
                    {
                        # Missing required 'Name' field
                        "Categories": [{"Name": "Test"}],
                        "Live": True
                    }
                ]
            }
        ]
    }
    
    # Act
    result = builtwith_service._process_technology_data(BuiltWithResponse(**invalid_response))
    
    # Assert
    assert isinstance(result, TechnologyProfile)
    assert len(result.technologies) == 0
    assert result.meta["domain"] == "example.com"

@pytest.mark.asyncio
async def test_api_error_handling(builtwith_service, mock_cache_service):
    # Arrange
    mock_cache_service.cached_request = AsyncMock(return_value=({}, 500))
    
    # Act & Assert
    with pytest.raises(RetryableError, match="API request failed with status 500"):
        await builtwith_service.get_technology_profile("example.com")
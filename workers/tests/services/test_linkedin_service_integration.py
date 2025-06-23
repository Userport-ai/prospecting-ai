import os
import sys
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

# Add the root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from services.linkedin_service import LinkedInService, LinkedInReaction, ActorRunFailed
from services.ai.api_cache_service import APICacheService, cached_request
from services.bigquery_service import BigQueryService

# Check if integration tests should be skipped (default: True)
SKIP_INTEGRATION_TESTS = os.environ.get('RUN_INTEGRATION_TESTS') != '1'

# Test LinkedIn profile to use for integration tests
TEST_LINKEDIN_PROFILE = "https://www.linkedin.com/in/satyanadella/"


@pytest.fixture
def test_profile_url():
    """Return a LinkedIn profile URL for testing."""
    profile = os.environ.get('TEST_LINKEDIN_PROFILE', TEST_LINKEDIN_PROFILE)
    return profile


@pytest.fixture
def mock_dependencies():
    """Mock the dependencies that would normally access BigQuery."""
    # Create mocks for the BigQuery and cache service
    mock_cache_service = AsyncMock(spec=APICacheService)
    mock_cache_service.get_cached_response = AsyncMock(return_value=None)
    mock_cache_service.cache_response = AsyncMock()
    
    # Patch the cached_request function to bypass caching
    mock_cached_request = AsyncMock(return_value=(None, 404))  # Simulate cache miss
    
    # Yield the mocks
    yield {
        'cache_service': mock_cache_service,
        'cached_request': mock_cached_request
    }


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason="Integration tests are disabled")
@pytest.mark.asyncio
async def test_apify_api_key_available():
    """Test that the APIFY_API_KEY is available in the environment."""
    api_key = os.getenv('APIFY_API_KEY')
    assert api_key is not None, "APIFY_API_KEY not set in environment"
    assert len(api_key) > 0, "APIFY_API_KEY is empty"


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason="Integration tests are disabled")
@pytest.mark.asyncio
async def test_fetch_reactions_real_api(test_profile_url, mock_dependencies):
    """Test fetching LinkedIn reactions with real API."""
    with patch.object(BigQueryService, '__init__', return_value=None), \
         patch.object(APICacheService, '__init__', return_value=None), \
         patch('services.linkedin_service.cached_request', mock_dependencies['cached_request']):
        
        # Create LinkedIn service
        service = LinkedInService()
        service.cache_service = mock_dependencies['cache_service']
        
        # Make the actual API call
        start_time = datetime.now()
        reactions = await service.fetch_reactions(test_profile_url, force_refresh=True)
        duration = (datetime.now() - start_time).total_seconds()
        
        # Basic validations
        assert reactions is not None, "Failed to get reactions"
        assert isinstance(reactions, list), "Response should be a list"
        
        # Print information about received reactions for debugging
        print(f"\nReceived {len(reactions)} reactions from LinkedIn API in {duration:.2f} seconds")
        if reactions:
            # Print sample reaction
            print(f"Sample reaction: {reactions[0].action}")
            
            # Verify structure of a reaction
            sample = reactions[0]
            assert isinstance(sample, LinkedInReaction), "Should be LinkedInReaction object"
            assert hasattr(sample, 'action'), "Reaction should have action"
            
            # Additional validations when author data is present
            if sample.author:
                print(f"Author: {sample.author.firstName} {sample.author.lastName}")
                assert sample.author.firstName or sample.author.lastName, "Author should have name"
        
        # Verify cache service was called to save the results
        service.cache_service.cache_response.assert_called_once()


@pytest.mark.skipif(SKIP_INTEGRATION_TESTS, reason="Integration tests are disabled")
@pytest.mark.asyncio
async def test_invalid_profile_handling(mock_dependencies):
    """Test handling of invalid LinkedIn profile URLs."""
    with patch.object(BigQueryService, '__init__', return_value=None), \
         patch.object(APICacheService, '__init__', return_value=None), \
         patch('services.linkedin_service.cached_request', mock_dependencies['cached_request']):
         
        service = LinkedInService()
        service.cache_service = mock_dependencies['cache_service']
        
        invalid_urls = [
            "https://linkedin.com/johndoe",  # Missing "/in/"
            "https://www.linkedin.com/company/microsoft",  # Company URL, not profile
            "https://example.com",  # Not LinkedIn at all
        ]
        
        for url in invalid_urls:
            with pytest.raises(ActorRunFailed) as exc_info:
                await service.fetch_reactions(url)
            
            # Check the error message contains information about invalid URL
            print(f"\nExpected error for {url}: {str(exc_info.value)}")
            assert "Invalid lead LinkedIn URL format" in str(exc_info.value)
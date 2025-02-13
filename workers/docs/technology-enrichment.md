# Technology Stack Enrichment

This document describes the technology stack enrichment feature that uses BuiltWith to detect and analyze technologies used by target accounts.

## Overview

The technology enrichment feature fetches and analyzes the technology stack of a company's website using the BuiltWith API. This information can be valuable for:
- Understanding a prospect's technical infrastructure
- Identifying technology-based sales opportunities
- Segmenting accounts based on technology usage
- Targeting companies using specific technologies

## Data Structure

### Technology Profile
```json
{
  "categories": {
    "JavaScript Frameworks": ["React", "Vue.js"],
    "Analytics": ["Google Analytics"],
    "Cloud Services": ["AWS"]
  },
  "technologies": ["React", "Vue.js", "Google Analytics", "AWS"],
  "confidence_scores": {
    "React": 0.9,
    "Vue.js": 0.8,
    "Google Analytics": 0.95,
    "AWS": 0.7
  },
  "meta": {
    "domain": "example.com",
    "last_scan": "2024-01-01T00:00:00Z"
  }
}
```

### Quality Metrics
```json
{
  "technology_count": 4,
  "category_count": 3,
  "average_confidence": 0.85,
  "detection_quality": "high",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## Usage

### 1. Triggering Enrichment

```python
# Using the Django API
response = requests.post(
    "api/v1/tasks/create/technology_enrichment_builtwith",
    json={
        "account_id": "account-uuid",
        "account_data": {
            "website": "https://example.com"
        }
    }
)
```

### 2. Checking Status

```python
response = requests.get(
    f"api/v1/tasks/{job_id}/status"
)
```

### 3. Accessing Results

The enrichment results are stored in:
1. The Account model's `technologies` field
2. BigQuery raw data storage
3. The AccountEnrichmentStatus model

## Configuration

### Environment Variables
- `BUILTWITH_API_KEY`: Your BuiltWith API key (required)

### Django Settings
No additional Django settings required.

## Quality Metrics

The enrichment process includes quality metrics to help assess the reliability of the technology detection:

### Detection Quality Levels
- **High**: 5+ technologies detected with avg confidence ≥ 0.7
- **Medium**: 3+ technologies detected with avg confidence ≥ 0.5
- **Low**: Fewer technologies or lower confidence
- **Insufficient Data**: No technologies detected

### Confidence Score Factors
1. Live Detection (0.3)
2. Detection Consistency (0.1)
3. Multiple Path Detection (up to 0.1)
4. Base Score (0.5)

## Error Handling

### Common Error Cases
1. Invalid or missing website URL
2. Rate limiting from BuiltWith API
3. Domain not found
4. API timeout

### Error Response Example
```json
{
  "status": "failed",
  "error_details": {
    "error_type": "ValueError",
    "message": "Invalid website URL",
    "stage": "initialization"
  }
}
```

## Callback Processing

The enrichment process sends callbacks at various stages:

1. **Initialization (10%)**
   - Task received and validated

2. **Data Fetching (50%)**
   - Technology data retrieved from BuiltWith
   - Initial processing complete

3. **Completion (100%)**
   - Data stored and processed
   - Quality metrics calculated

### Callback Payload Example
```json
{
  "job_id": "job-uuid",
  "account_id": "account-uuid",
  "enrichment_type": "technology_info",
  "source": "builtwith",
  "status": "completed",
  "completion_percentage": 100,
  "processed_data": {
    "technology_data": {...},
    "quality_metrics": {...},
    "processing_time": 1.23
  }
}
```

## Best Practices

1. **Website URLs**
   - Always provide clean, valid URLs
   - Include protocol (http/https)
   - Remove query parameters and fragments

2. **Rate Limiting**
   - Monitor API usage
   - Implement appropriate retry strategies
   - Cache results when possible

3. **Data Quality**
   - Check confidence scores before using data
   - Consider multiple data points for critical decisions
   - Regularly refresh technology data (recommended: monthly)

## Limitations

1. **Detection Accuracy**
   - Some technologies may not be detectable
   - False positives possible (though rare)
   - Version information may not always be available

2. **API Constraints**
   - Rate limits apply
   - Some domains may be blocked/unavailable
   - Response times can vary

3. **Data Freshness**
   - Data is cached for 7 days
   - Real-time detection not available

## Integration Examples

### 1. Filtering Accounts by Technology
```python
accounts = Account.objects.filter(
    technologies__contains=["React"]
)
```

### 2. Getting High-Quality Technology Data
```python
enrichment_status = AccountEnrichmentStatus.objects.get(
    account=account,
    enrichment_type="technology_info"
)
if (
    enrichment_status.status == "completed" and
    enrichment_status.data_quality_score >= 0.7
):
    technologies = account.technologies
```

### 3. Scheduling Regular Updates
```python
from datetime import timedelta

accounts_to_update = Account.objects.filter(
    enrichment_statuses__enrichment_type="technology_info",
    enrichment_statuses__last_successful_run__lte=timezone.now() - timedelta(days=30)
)
```

## Troubleshooting

### Common Issues

1. **No Technologies Detected**
   - Verify website is accessible
   - Check if website uses client-side rendering
   - Ensure domain is correct

2. **Low Confidence Scores**
   - Website might be using uncommon technologies
   - Technology might be partially implemented
   - Check if website is fully loaded

3. **API Errors**
   - Verify API key is valid
   - Check rate limits
   - Ensure network connectivity

### Debugging Steps

1. Check the enrichment status and error details
2. Verify the website is accessible
3. Look for patterns in failed detections
4. Review BigQuery raw data for detailed API responses

## Support

For issues or questions:
1. Check the error details in AccountEnrichmentStatus
2. Review BigQuery logs for raw API responses
3. Contact the development team with job_id and account_id